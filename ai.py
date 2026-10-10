"""OpenAI-compatible API transport. No API keys are exported or logged."""
import ctypes, json, os, threading
from ctypes import wintypes
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

class APIError(Exception): pass
class BudgetError(APIError): pass

class Blob(ctypes.Structure):
 _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]

def protect(data, decrypt=False):
 if os.name!='nt': raise APIError('此版本使用 Windows 用户账户加密保存密钥')
 raw=ctypes.create_string_buffer(data); src=Blob(len(data),ctypes.cast(raw,ctypes.POINTER(ctypes.c_ubyte))); dest=Blob()
 crypt=ctypes.WinDLL('crypt32',use_last_error=True); kernel=ctypes.WinDLL('kernel32',use_last_error=True)
 function=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
 function.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
 function.restype=wintypes.BOOL
 kernel.LocalFree.argtypes=[ctypes.c_void_p]; kernel.LocalFree.restype=ctypes.c_void_p
 if not function(ctypes.byref(src),None,None,None,None,1,ctypes.byref(dest)): raise APIError('无法加密或读取 API 密钥，请重新保存设置')
 try: return ctypes.string_at(dest.data,dest.size)
 finally: kernel.LocalFree(dest.data)

class Vault:
 def __init__(self,path): self.path=Path(path); self.lock=threading.Lock()
 def read(self):
  if not self.path.exists(): return {}
  return json.loads(protect(self.path.read_bytes(),True).decode())
 def get(self,pid):
  with self.lock: return self.read().get(pid,'')
 def set(self,pid,key):
  with self.lock:
   data=self.read(); data[pid]=key; self.path.parent.mkdir(parents=True,exist_ok=True)
   temp=self.path.with_suffix('.tmp'); temp.write_bytes(protect(json.dumps(data).encode())); os.replace(temp,self.path)
 def has(self,pid):
  try: return bool(self.get(pid))
  except (APIError,ValueError,OSError): return False

class Provider:
 def __init__(self,store,vault): self.store=store; self.vault=vault
 def active(self):
  pid=self.store.settings()['active_provider']
  return next((p for p in self.store.providers() if p['id']==pid),None)
 def ready(self):
  if self.store.settings()['ai_mode']=='web':return False
  p=self.active()
  return bool(p and self.vault.has(p['id']))
 def request(self,profile,messages,purpose='chat',structured=False):
  key=self.vault.get(profile['id'])
  if not key: raise APIError('请在设置中填写并保存 API 密钥')
  uid=self.store.reserve_call(profile['id'],purpose)
  if uid is None: raise BudgetError('已达到今天的 API 调用上限，明天自动继续；也可在设置中调整上限')
  model=profile['organizer_model'] if purpose!='chat' else profile['model']
  payload={'model':model,'messages':messages}
  settings=self.store.settings()
  payload['max_completion_tokens' if model.startswith(('gpt-5','gpt-6','o1','o3','o4')) else 'max_tokens']=settings['organize_tokens'] if structured else 128
  request=Request(profile['base_url']+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key},method='POST')
  try:
   with urlopen(request,timeout=45) as response:
    raw=response.read(2_000_001)
    if len(raw)>2_000_000: raise APIError('API 返回内容过大')
    data=json.loads(raw)
   self.store.update_tokens(uid,data.get('usage',{}).get('total_tokens',0))
   if structured and data['choices'][0].get('finish_reason')=='length':raise APIError('整理输出达到 token 上限，输入仍保留；请提高整理输出上限后重试')
   content=data['choices'][0]['message']['content']
   if isinstance(content,list): content=''.join(str(p.get('text','')) for p in content if isinstance(p,dict))
   if not isinstance(content,str) or not content.strip(): raise APIError('模型返回空内容，请检查所选模型')
   if structured:
    stripped=content.strip()
    if stripped.startswith('```'): stripped='\n'.join(stripped.splitlines()[1:-1])
    try: result=json.loads(stripped)
    except json.JSONDecodeError: raise APIError('整理模型没有返回有效 JSON，任务已保留，可更换模型后重试')
    if not isinstance(result,dict): raise APIError('整理结果格式无效')
    return result
   return content.strip()
  except HTTPError as e:
   raise APIError('API 返回 HTTP '+str(e.code)+'；请检查服务地址、密钥、模型和账户余额') from None
  except (URLError,TimeoutError,OSError): raise APIError('API 连接失败或超时；请检查地址与网络') from None
  except (ValueError,KeyError,IndexError,TypeError): raise APIError('API 返回格式不兼容，请使用 Chat Completions 兼容接口') from None
 def call(self,messages,purpose='chat',structured=False):
  if self.store.settings()['ai_mode']=='web':raise APIError('网页模式请在设置中准备整理内容，并粘贴网页 AI 的回复')
  p=self.active()
  if not p: raise APIError('尚未选择 AI 配置')
  return self.request(p,messages,purpose,structured)
