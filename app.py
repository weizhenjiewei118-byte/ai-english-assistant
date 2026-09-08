# -*- coding: utf-8 -*-
"""
AI英语学习助手 —— Flask 后端

功能：
    1. 托管前端静态页面（index.html / css / js）
    2. 提供 /api/process 接口，接收 { text, actionType }，返回 { result }
    3. 未配置 AI 密钥时返回“模拟结果”，配置后调用真实大模型 API

运行方式：
    pip install -r requirements.txt
    python app.py
    然后浏览器打开 http://127.0.0.1:5000
"""

import json
import urllib.request
import urllib.error

from flask import Flask, request, jsonify

# ============================================================
# AI 服务配置（请自行填入密钥；兼容 OpenAI 接口格式的大模型）
#   OpenAI   : BASE_URL = https://api.openai.com/v1
#   DeepSeek : BASE_URL = https://api.deepseek.com/v1
#   智谱 GLM : BASE_URL = https://open.bigmodel.cn/api/paas/v4
#   通义千问 : BASE_URL = https://dashscope.aliyuncs.com/compatible-mode/v1
# ============================================================
# 密钥优先从本地私有配置 config_local.py 读取（该文件已加入 .gitignore，不会上传 GitHub）；
# 若该文件不存在（例如他人刚克隆仓库），则使用下方占位符：
# 自行创建 config_local.py 填入 AI_API_KEY / AI_BASE_URL / AI_MODEL 即可
try:
    from config_local import AI_API_KEY, AI_BASE_URL, AI_MODEL  # type: ignore
except ImportError:
    AI_API_KEY = "sk-在这里填入你的密钥"        # TODO: 替换为你自己的 API Key
    AI_BASE_URL = "https://api.deepseek.com/v1"  # TODO: 按需替换服务商地址
    AI_MODEL = "deepseek-chat"                   # TODO: 按需替换模型名
# ============================================================

# 把当前目录作为静态资源目录，使 index.html 用相对路径引用 css/js
# （这样直接双击 index.html 也能打开页面，接口请求失败时前端会自动降级为本地模拟）
app = Flask(__name__, static_folder=".", static_url_path="")

# 三种功能对应的系统提示词
PROMPTS = {
    "polish": (
        "你是一位专业的英语写作老师。请润色用户提交的英文句子或作文，要求：\n"
        "1. 修正语法、拼写和标点错误；\n"
        "2. 让表达更地道、更符合英语母语使用者的书面习惯；\n"
        "3. 先给出【润色后】的完整文本，再用【修改说明】逐条列出关键改动及理由；\n"
        "4. 说明部分使用中文，英文原文保持不变。"
    ),
    "analyze": (
        "你是一位擅长讲解长难句的英语老师。请解析用户给出的英文句子，结果包含：\n"
        "1.【句子主干】找出主句的主语、谓语、宾语；\n"
        "2.【结构拆分】说明从句、非谓语动词、介词短语等修饰成分及其作用；\n"
        "3.【重点词汇】列出句中的重点单词、词性及中文含义；\n"
        "4.【参考翻译】给出通顺准确的中文翻译。\n"
        "讲解使用中文，条理清晰，适合学生理解。"
    ),
    "flashcard": (
        "你是一位英语词汇教学专家。请根据用户输入的英文单词或句子，生成一张便于背诵的记忆卡片，包含：\n"
        "1. 单词/短语、音标、词性；\n"
        "2. 中文释义（含常用搭配）；\n"
        "3. 一个地道的英文例句及其中文翻译；\n"
        "4. 一条实用的记忆技巧（词根词缀 / 联想记忆 / 易混词辨析均可）。\n"
        "排版清晰，使用 emoji 分节，适合直接抄写背诵。"
    ),
}

# 功能中文名（用于模拟结果展示）
ACTION_LABELS = {
    "polish": "润色作文",
    "analyze": "解析长难句",
    "flashcard": "生成记忆卡片",
}


def mock_result(action_type, text):
    """本地模拟结果：不依赖 AI 服务，保证开箱即用的演示闭环。"""
    if action_type == "polish":
        return (
            "【润色后】\n{text}\n\n"
            "【修改说明】\n"
            "1. 语法检查：模拟模式下未发现明显语法错误；\n"
            "2. 表达升级：建议把口语化词汇替换为更地道的书面表达；\n"
            "3. 句式优化：可适当使用从句或分词结构，避免句式单一。\n\n"
            "（当前为模拟结果。在 app.py 中填入 AI_API_KEY 后，即可获得针对你原文的"
            "逐句润色与详细修改理由。）"
        ).format(text=text)

    if action_type == "analyze":
        return (
            "【原句】\n{text}\n\n"
            "【句子主干】\n"
            "主语 + 谓语 + 宾语（模拟解析，未真正分析语法结构）。\n\n"
            "【结构拆分】\n"
            "· 从句 / 非谓语 / 介词短语等修饰成分将在此逐层说明；\n"
            "· 时态、语态与逻辑关系将在此标注。\n\n"
            "【重点词汇】\n"
            "· 句中的重点单词、词性及中文释义将在此列出。\n\n"
            "【参考翻译】\n"
            "（模拟翻译，配置真实 AI 后可获得完整准确的中文译文。）"
        ).format(text=text)

    # flashcard
    # 取输入中的第一个单词作为卡片词条；若输入的是整句，则直接以整句为例句
    first_word = text.strip().split()[0].strip(".,!?;:\"'").capitalize() if text.strip() else "Word"
    example = text if " " in text.strip() else "Please remember this word in a real sentence."
    return (
        "🃏 记忆卡片\n\n"
        "🔤 单词：{word}\n"
        "📢 音标：[ ˈ…… ]（模拟）\n"
        "🏷️ 词性：n. / v. / adj.\n"
        "📝 释义：（模拟中文释义，配置 AI 后生成真实释义与常用搭配）\n"
        "📚 例句：{example}\n"
        "💡 记忆技巧：结合词根词缀与例句语境记忆，效果更佳。\n\n"
        "（当前为模拟结果，配置真实 AI 后将生成完整的音标、释义与助记内容。）"
    ).format(word=first_word, example=example)


def call_ai(system_prompt, user_text):
    """调用 OpenAI 兼容格式的大模型接口（使用标准库 urllib，无需额外依赖）。"""
    url = AI_BASE_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.7,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + AI_API_KEY,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def ai_configured():
    """判断用户是否已经填入真实密钥（占位符或空值视为未配置）。"""
    return bool(AI_API_KEY) and not AI_API_KEY.startswith("sk-在这里")


@app.route("/")
def index():
    """根路径返回前端首页。"""
    return app.send_static_file("index.html")


@app.route("/api/process", methods=["POST"])
def api_process():
    """统一处理接口：接收 { text, actionType }，返回 { result }。"""
    data = request.get_json(silent=True) or {}
    text = str(data.get("text", "")).strip()
    action_type = data.get("actionType", "")

    # ---- 参数校验 ----
    if not text:
        return jsonify({"error": "请先输入英文句子或单词～"}), 400
    if len(text) > 2000:
        return jsonify({"error": "输入内容过长，请控制在 2000 字符以内。"}), 400
    if action_type not in PROMPTS:
        return jsonify({"error": "未知的功能类型：%s" % action_type}), 400

    # ---- 未配置密钥：直接返回模拟结果 ----
    if not ai_configured():
        return jsonify({"result": mock_result(action_type, text), "mode": "mock"})

    # ---- 调用真实 AI；失败时降级为模拟结果，保证页面不报错 ----
    try:
        result = call_ai(PROMPTS[action_type], text)
        return jsonify({"result": result, "mode": "ai"})
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, TimeoutError) as e:
        fallback = mock_result(action_type, text)
        return jsonify({
            "result": fallback + "\n\n（AI 服务调用失败：%s，已自动切换为模拟结果。）" % e,
            "mode": "mock",
        })


if __name__ == "__main__":
    # 调试模式启动；正式部署可改用 waitress / gunicorn
    app.run(host="127.0.0.1", port=5000, debug=True)
