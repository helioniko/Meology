"""Stable profile keys and a factual, optional onboarding questionnaire.

Labels and questions may change; a key must never be reused for another meaning.
Answers are stored once in records. Questionnaire progress contains no answers.
"""
from datetime import date
import math

PROFILE_SCHEMA_VERSION = 3
QUESTIONNAIRE_VERSION = 1


def question(key, label, prompt, kind='text', example='', choices=(), low=None, high=None):
    return dict(key=key, label=label, prompt=prompt, type=kind, example=example,
                choices=list(choices), minimum=low, maximum=high)


def group(key, label, description, topics, questions, share=True):
    return dict(id=key, label=label, description=description, topics=topics,
                share_default=share, questions=questions)


GROUPS = [
    group('basic', '基本情况', '称呼、生日、城市和常用语言', ['生活', '交流'], [
        question('name', '称呼', '希望怎么称呼你？', example='昵称或姓名都可以'),
        question('birth_date', '出生日期', '你的出生日期是？', 'date'),
        question('birthplace', '出生地', '你出生在哪个城市？', example='只填城市即可'),
        question('city', '所在地', '现在主要住在哪个城市？', example='例如：杭州'),
        question('languages', '常用语言', '平时使用哪些语言？', example='例如：普通话、英语、粤语'),
    ]),
    group('education', '学习与教育', '在读情况、学校、专业和正在学习的内容', ['学习'], [
        question('education_status', '在读情况', '你目前在上学吗？', 'select', choices=['正在上学', '已经毕业', '暂时休学', '目前未入学']),
        question('school', '学校与专业', '目前或最近就读的学校是？', example='学校名称即可，也可以附专业'),
        question('education_level', '教育阶段', '目前或最近的教育阶段是？', 'select', choices=['小学', '初中', '高中', '中职 / 中专', '专科', '本科', '硕士', '博士', '其他']),
        question('major', '专业', '所学专业叫什么？', example='没有专业可以留空'),
        question('study_topics', '正在学习', '最近在学什么课程或知识？', example='例如：英语四级、Python 入门'),
    ]),
    group('work', '工作情况', '就业情况、单位、岗位和开始工作的年份', ['工作'], [
        question('employment_status', '就业情况', '你目前的工作状态是？', 'select', choices=['在单位工作', '自由职业', '自己创业', '正在找工作', '暂未工作', '已退休']),
        question('workplace', '工作单位', '目前的工作单位叫什么？', example='公司、组织或店铺名称；没有就留空'),
        question('job_title', '岗位 / 职业', '目前的岗位或职业叫什么？', example='例如：设计师、销售、软件工程师'),
        question('work_start_year', '开始工作年份', '你第一次正式工作是哪一年？', 'number', low=1900, high='current_year'),
    ]),
    group('skills', '技能与工具', '实际用过的技能、工具和已取得的证书', ['工作', '学习'], [
        question('skills', '技能与擅长的事', '你实际做过哪些技能相关的事情？', 'textarea', '例如：能做 Excel 报表、开车、拍摄剪辑；不用评价自己有多优秀'),
        question('tools', '使用过的工具', '你经常使用哪些软件、设备或工具？', 'textarea', '例如：Photoshop、Python、相机'),
        question('certificates', '证书与资格', '你已经取得哪些证书或资格？', 'textarea', '例如：驾照 C1、英语六级；没有可以留空'),
    ]),
    group('achievements', '成果与作品', '完成的项目、作品、奖项和时间', ['项目', '工作'], [
        question('achievements', '成果、作品与重要经历', '你完成过哪些想记录的作品或项目？', 'textarea', '例如：2025 年做过一个个人网站；可以只写一件'),
        question('awards', '获得的奖项', '你获得过哪些奖项？', 'textarea', '例如：2024 年校级数学竞赛二等奖；没有可以留空'),
    ]),
    group('family', '家庭与关系', '家庭成员、同住情况和照顾责任', ['关系'], [
        question('family_members', '家庭成员', '你想记录哪些家庭成员？', 'textarea', '例如：父母、一个妹妹；称呼即可，不用实名'),
        question('household_members', '同住情况', '现在和谁一起住？', example='例如：独居、与父母同住、与室友合住'),
        question('relationship_status', '伴侣情况', '你目前的伴侣情况是？', 'select', choices=['没有伴侣', '有伴侣', '已婚', '已离异', '丧偶']),
        question('care_responsibilities', '照顾责任', '目前需要长期照顾谁或什么？', 'textarea', '例如：照顾孩子、照顾老人、养一只猫；没有可以留空'),
    ], share=False),
    group('history', '过去的经历', '曾住的城市、学习和工作经历、人生事件', ['生活', '学习', '工作'], [
        question('past_cities', '曾居住的城市', '你曾经长期住过哪些城市？', example='例如：2010—2018 年南京，2018 年起杭州'),
        question('education_history', '学习经历', '你愿意记录哪些过去的学习经历？', 'textarea', '例如：2018—2022 年，某大学，计算机专业'),
        question('work_history', '工作经历', '你愿意记录哪些过去的工作经历？', 'textarea', '例如：2022—2024 年，某公司，设计师'),
        question('life_events', '已发生的人生事件', '有哪些已发生的事情你愿意记下来？', 'textarea', '按“年份 + 事情”写即可，例如：2023 年搬家、2024 年结婚；不用总结影响'),
    ]),
    group('health', '身体与健康', '身高、体重和已经知道的健康情况', ['健康'], [
        question('height_cm', '身高（厘米）', '你的身高是多少厘米？', 'number', low=30, high=280),
        question('weight_kg', '体重（千克）', '最近知道的体重是多少千克？', 'number', low=1, high=500),
        question('known_allergies', '已知过敏', '你已知对哪些东西过敏？', example='例如：花生、青霉素；不清楚就留空'),
        question('chronic_conditions', '已知健康情况', '有哪些已确诊的健康情况你愿意记录？', 'textarea', '填写你已知道的情况；不用猜测或自行诊断'),
        question('accessibility_needs', '日常辅助需要', '日常需要哪些辅助用品或便利条件？', example='例如：眼镜、助听器、无障碍通道'),
    ], share=False),
    group('habits', '生活习惯', '通常的作息、运动次数和饮食要求', ['生活', '健康', '偏好'], [
        question('usual_sleep_time', '通常睡觉时间', '平时大概几点睡觉？', 'time'),
        question('usual_wake_time', '通常起床时间', '平时大概几点起床？', 'time'),
        question('exercise_frequency', '每周运动次数', '平时每周运动多少次？', 'select', choices=['通常不运动', '1—2 次', '3—4 次', '5 次及以上', '没有固定频率']),
        question('dietary_requirements', '饮食要求', '平时有哪些明确的饮食要求？', example='例如：素食、不喝酒、不吃辣；没有可以留空'),
    ]),
    group('interests', '兴趣与喜好', '经常做的活动、喜欢和不喜欢的食物、内容', ['偏好', '生活'], [
        question('hobbies', '兴趣活动', '有空时你经常做哪些活动？', example='例如：跑步、游戏、看电影、做饭'),
        question('favorite_foods', '喜欢的食物', '你喜欢吃哪些东西？', example='写几种就可以'),
        question('disliked_foods', '不喜欢的食物', '有哪些你不喜欢吃的东西？', example='不清楚就留空'),
        question('favorite_media', '常看的内容', '你经常看哪些书、影片或频道？', 'textarea', '写名称或类型即可，例如：科幻小说、历史纪录片'),
    ]),
    group('resources', '居住与可用资源', '居住情况、通勤、消费预算和可用设备', ['生活', '财务', '工作'], [
        question('housing_status', '居住情况', '你目前的居住情况是？', 'select', choices=['租房', '自有住房', '学校宿舍', '单位宿舍', '与家人同住', '其他']),
        question('commute_minutes', '单程通勤分钟', '通常单程通勤大约多少分钟？', 'number', low=0, high=600),
        question('monthly_budget', '每月消费预算', '每月可用于自己消费的预算大约是多少？', example='例如：2000—3000 元；不方便回答就留空'),
        question('available_equipment', '可用设备', '平时有哪些可以使用的设备？', example='例如：Windows 电脑、手机、相机'),
    ], share=False),
    group('plans', '近期计划', '正在做的事、明确想完成的事和可用时间', ['目标', '项目'], [
        question('current_projects', '正在做的事情', '你目前正在做哪些事情或项目？', 'textarea', '例如：准备驾照考试、做个人网站'),
        question('near_term_goal', '近期想完成的事', '接下来想完成哪一件具体的事？', example='例如：通过英语四级；没想好就留空'),
        question('goal_deadline', '计划完成日期', '如果有计划，打算哪天完成？', 'date'),
        question('weekly_free_hours', '每周可用小时', '每周大约能拿出多少小时做自己的事？', 'number', low=0, high=168),
    ]),
    group('communication', 'AI 回答方式', '回答长度、排版和称呼方式', ['交流'], [
        question('communication', '希望 AI 怎样与你交流', '你更喜欢哪种回答方式？', 'select', choices=['简短直接，先给结论', '适中解释，再给建议', '详细说明，给出步骤']),
        question('answer_format', '回答排版', '你更喜欢哪种排版？', 'select', choices=['自然段落', '分点列表', '按步骤说明', '都可以']),
        question('address_style', '称呼方式', 'AI 和你说话时，用哪个称呼？', 'select', choices=['你', '您', '使用我的昵称']),
    ]),
]
GROUP_MAP = {g['id']: g for g in GROUPS}
QUESTIONS = {q['key']: q for g in GROUPS for q in g['questions']}
# These fields are deliberately absent from initial questions. AI suggestions require review.
LEARNED_FIELDS = [
    ('values', '价值观与决策原则', '从记录逐步理解', 'textarea'),
    ('preferences', '综合偏好', '从记录逐步理解', 'textarea'),
    ('boundaries', '重要边界与不能接受的事', '从记录逐步理解', 'textarea'),
    ('goals', '长期目标', '从记录逐步理解', 'textarea'),
    ('constraints', '现实约束', '从记录逐步理解', 'textarea'),
    ('thinking_patterns', '思考与行动模式', '从记录逐步理解', 'textarea'),
    ('emotional_patterns', '反复出现的情绪体验', '从记录逐步理解', 'textarea'),
]
# Retained semantic key for combined history; newer answers may use more specific keys.
LEGACY_FIELDS = [('experience', '学习与工作经历', '过去的经历', 'textarea')]
FIELDS = [(q['key'], q['label'], g['label'], q['type'] if q['type'] != 'select' else 'text')
          for g in GROUPS for q in g['questions']] + LEGACY_FIELDS + LEARNED_FIELDS
FIELD_MAP = {f[0]: f for f in FIELDS}
FIELD_TOPICS = {q['key']: g['topics'] for g in GROUPS for q in g['questions']}
FIELD_TOPICS.update(dict(name=['交流'], birth_date=['健康'], height_cm=['健康'],
                         values=['决策', '工作', '学习'], preferences=['偏好', '生活'],
                         boundaries=['偏好', '决策'], goals=['目标'], constraints=['目标', '财务'],
                         experience=['学习', '工作'], thinking_patterns=['决策'], emotional_patterns=['关系', '健康']))


def validate_answer(key, value, strict_choice=False):
    if key not in FIELD_MAP or not isinstance(value, str):
        raise ValueError('档案字段或内容无效')
    value = value.strip()
    if len(value) > 3000:
        raise ValueError('单项档案不能超过 3000 字')
    if not value:
        return value
    q = QUESTIONS.get(key)
    if q:
        if strict_choice and q['choices'] and value not in q['choices']:
            raise ValueError('请选择列表中的答案，或暂不填写')
        if q['type'] == 'number':
            try:
                number = float(value)
            except ValueError:
                raise ValueError(q['label'] + '请填写数字') from None
            high = date.today().year if q['maximum'] == 'current_year' else q['maximum']
            if not math.isfinite(number) or (q['minimum'] is not None and number < q['minimum']) or (high is not None and number > high):
                raise ValueError('请检查' + q['label'] + '数值')
            if key == 'work_start_year' and not number.is_integer():
                raise ValueError('工作年份请填写完整年份')
        if q['type'] == 'date':
            try:
                day = date.fromisoformat(value)
            except ValueError:
                raise ValueError(q['label'] + '请填写有效日期') from None
            value = day.isoformat()
            if key == 'birth_date' and day > date.today():
                raise ValueError('出生日期不能在未来')
        if q['type'] == 'time':
            from datetime import datetime
            try:
                value = datetime.strptime(value, '%H:%M').strftime('%H:%M')
            except ValueError:
                raise ValueError('时间请使用 HH:MM 格式') from None
    return value


def check_profile_metadata(c):
    """Unknown future semantic formats must not be overwritten or imported."""
    import json
    from data_format import DataFormatError
    row = c.execute("SELECT value FROM metadata WHERE key='profile_schema_version'").fetchone()
    if row:
        try:
            version = int(row[0])
        except (ValueError, TypeError):
            raise DataFormatError('个人档案格式版本无效') from None
        if not 1 <= version <= PROFILE_SCHEMA_VERSION:
            raise DataFormatError('个人档案来自未支持的版本，请先升级软件')
    watermark=c.execute("SELECT value FROM metadata WHERE key='record_id_highwater'").fetchone()
    if watermark and (not watermark[0].isascii() or not watermark[0].isdecimal() or not 0<=int(watermark[0])<2**63-1):
        raise DataFormatError('记录编号保留标记无效')
    from dossier import check_metadata
    check_metadata(c)
    from agenda import check_metadata as check_agenda
    check_agenda(c)
    row = c.execute("SELECT value FROM metadata WHERE key='onboarding'").fetchone()
    if row:
        try:
            progress = json.loads(row[0])
        except (ValueError, TypeError):
            raise DataFormatError('建档进度格式无效') from None
        if not isinstance(progress, dict) or type(progress.get('version')) is not int or progress['version'] != QUESTIONNAIRE_VERSION:
            raise DataFormatError('建档进度来自未支持的版本，请升级软件')
        selected = progress.get('selected')
        if not isinstance(selected, list) or any(not isinstance(g, str) or g not in GROUP_MAP for g in selected) or len(set(selected)) != len(selected):
            raise DataFormatError('建档方向信息无效')
        current = progress.get('current_group')
        if not isinstance(current, str) or (current and current not in selected) or type(progress.get('in_progress')) is not bool:
            raise DataFormatError('建档位置或状态无效')
