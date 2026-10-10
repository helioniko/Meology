"""UI localization only. Stable database keys and user content are never translated."""
import json,re
from functools import lru_cache
from app_runtime import RESOURCE_ROOT
@lru_cache(maxsize=1)
def english():
    return json.loads((RESOURCE_ROOT/'locales'/'en.json').read_text(encoding='utf-8'))
def translate(message,language='zh-CN'):
    return english().get(message,message) if language=='en' else message
def error_text(message,language='zh-CN'):
    value=translate(message,language)
    if language=='en' and re.search(r'[\u3400-\u9fff]',value):
        return 'Unable to complete this operation. Your data is retained. Check the input or settings and try again.'
    return value
