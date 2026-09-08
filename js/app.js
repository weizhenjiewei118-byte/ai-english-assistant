/* ==========================================================
   AI英语学习助手 —— 前端交互逻辑
   功能：获取输入 → 调用后端 /api/process → 展示结果
   兜底：后端未启动时（如直接双击打开 html），使用浏览器本地模拟结果
   ========================================================== */

// 三种功能的中文名（与后端 actionType 约定一致）
var ACTION_LABELS = {
  polish: "✍️ 润色作文结果",
  analyze: "🔍 长难句解析结果",
  flashcard: "🃏 记忆卡片"
};

// 快捷获取 DOM 元素
var inputEl = document.getElementById("inputText");
var loadingEl = document.getElementById("loading");
var resultCard = document.getElementById("resultCard");
var resultTag = document.getElementById("resultTag");
var resultBody = document.getElementById("resultBody");
var copyBtn = document.getElementById("copyBtn");
var actionBtns = document.querySelectorAll(".action-btn");

/**
 * 调用后端接口处理文本
 * @param {string} action - 功能类型：polish / analyze / flashcard
 */
async function processText(action) {
  var text = inputEl.value.trim();

  // 输入校验
  if (!text) {
    showResult("⚠️ 提示", "请先在上方输入框中输入英文句子或单词，再点击功能按钮～");
    inputEl.focus();
    return;
  }

  setLoading(true);

  try {
    // 调用 Flask 后端接口
    var resp = await fetch("/api/process", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text, actionType: action })
    });

    var data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || "请求失败，请稍后重试");
    }

    showResult(ACTION_LABELS[action], data.result);
  } catch (err) {
    // 后端不可用（未启动服务 / 直接打开 html）时，降级为本地模拟结果
    var mock = localMock(action, text) +
      "\n\n（提示：未连接后端服务，当前为浏览器本地模拟结果；启动 Flask 后可获得真实 AI 结果。）";
    showResult(ACTION_LABELS[action], mock);
  } finally {
    setLoading(false);
  }
}

/**
 * 切换加载状态（加载时禁用所有按钮，防止重复提交）
 */
function setLoading(loading) {
  loadingEl.hidden = !loading;
  actionBtns.forEach(function (btn) {
    btn.disabled = loading;
  });
}

/**
 * 在结果区域展示文本（使用 textContent 避免 XSS）
 */
function showResult(tag, content) {
  resultTag.textContent = tag;
  resultBody.textContent = content;
  resultCard.hidden = false;
  // 新结果出现时滚动到可视区域
  resultCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/**
 * 复制结果到剪贴板
 */
copyBtn.addEventListener("click", function () {
  var text = resultBody.textContent;
  if (!text) return;
  navigator.clipboard.writeText(text).then(function () {
    copyBtn.textContent = "✅ 已复制";
    setTimeout(function () { copyBtn.textContent = "📋 复制结果"; }, 1500);
  }).catch(function () {
    copyBtn.textContent = "❌ 复制失败";
    setTimeout(function () { copyBtn.textContent = "📋 复制结果"; }, 1500);
  });
});

// 绑定三个功能按钮的点击事件
actionBtns.forEach(function (btn) {
  btn.addEventListener("click", function () {
    processText(btn.getAttribute("data-action"));
  });
});

/* ----------------------------------------------------------
   以下为浏览器本地模拟结果（仅在后端不可用时兜底使用，
   逻辑与 app.py 中的 mock_result 保持一致）
   ---------------------------------------------------------- */
function localMock(action, text) {
  if (action === "polish") {
    return "【润色后】\n" + text + "\n\n" +
      "【修改说明】\n" +
      "1. 语法检查：模拟模式下未发现明显语法错误；\n" +
      "2. 表达升级：建议把口语化词汇替换为更地道的书面表达；\n" +
      "3. 句式优化：可适当使用从句或分词结构，避免句式单一。";
  }

  if (action === "analyze") {
    return "【原句】\n" + text + "\n\n" +
      "【句子主干】\n主语 + 谓语 + 宾语（模拟解析）。\n\n" +
      "【结构拆分】\n· 从句 / 非谓语 / 介词短语等修饰成分将在此逐层说明；\n\n" +
      "【重点词汇】\n· 句中的重点单词、词性及中文释义将在此列出。\n\n" +
      "【参考翻译】\n（模拟翻译，启动后端并配置 AI 密钥后可获得完整解析。）";
  }

  // flashcard
  var firstWord = text.trim().split(/\s+/)[0].replace(/[.,!?;:"']/g, "");
  firstWord = firstWord.charAt(0).toUpperCase() + firstWord.slice(1);
  var example = text.indexOf(" ") !== -1
    ? text
    : "Please remember this word in a real sentence.";

  return "🃏 记忆卡片\n\n" +
    "🔤 单词：" + firstWord + "\n" +
    "📢 音标：[ ˈ…… ]（模拟）\n" +
    "🏷️ 词性：n. / v. / adj.\n" +
    "📝 释义：（模拟中文释义，配置 AI 后生成真实释义与常用搭配）\n" +
    "📚 例句：" + example + "\n" +
    "💡 记忆技巧：结合词根词缀与例句语境记忆，效果更佳。";
}
