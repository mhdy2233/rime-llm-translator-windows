# 🚀 rime-llm-translator-windows

> **Windows (小狼毫 Weasel) 专用的 Rime 大模型拼音联想与指令增强扩展**  
> 0 弹黑框、0ms 日常打字穿透、键盘邻键智能容错三候选、集成丰富的前缀 AI 指令（问答/翻译/命令/猫娘）。

[![GitHub Release](https://img.shields.io/github/v/release/mhdy2233/rime-llm-translator-windows?style=flat-square&color=blue)](https://github.com/mhdy2233/rime-llm-translator-windows/releases/latest)
[![Download Standalone](https://img.shields.io/badge/下载-独立免安装版%20(无需Python)-success?style=flat-square&logo=windows)](https://github.com/mhdy2233/rime-llm-translator-windows/releases/latest/download/rime-llm-translator-windows-v1.0.0-standalone.zip)

---

## 💡 致谢与参考

本项目核心灵感与前缀设计理念参考了优秀的开源项目 **[SHORiN-KiWATA/rime-llm-translator](https://github.com/SHORiN-KiWATA/rime-llm-translator)**，在此向原作者致以由衷的感谢与敬意！

在 Windows 平台与小狼毫（Weasel）生态下，原 Linux/Fcitx5 架构存在若干系统级难题：
1. **`curl` 黑框弹窗**：Windows 下通过 Lua 调用系统命令极易弹出闪烁黑框；
2. **输入线程冻结**：Windows IME 主消息线程进行网络请求会造成按键卡死与严重吞字；
3. **冒号与标点截断**：小狼毫中文模式下输入 `:` 会被标点处理器强行截断并结算上屏；
4. **全角/半角时序冲突**：中文输入法下按 `Shift + ;` 极易打断拼音流。

**`rime-llm-translator-windows`** 专为 Windows / 小狼毫做了深度架构重构，彻底攻克上述所有痛点。

---

## ✨ 核心特性

- **🛡️ 纯静默 0 弹黑框**：采用原生无界面的后台守护进程（`pythonw`）与内存 IPC 交换，输入过程中绝无任何命令行黑框闪烁。
- **⚡ 0ms 日常穿透，绝不卡键盘**：平时正常码字 100% 走本地原生输入法引擎；仅在末尾双击 `vv` 时才按需唤醒大模型。未启动服务时自动穿透，打字体验丝滑跟手。
- **🎯 键盘邻键容错（置顶前 3 候选）**：
  - 常规长难句无前缀输入时，模型充分推测键盘物理邻键误触（如 `a/s/w` 误击）、漏拼、错音节、前后鼻音混淆；
  - 自动输出可能性最高的 **前 3 个纠错候选**，直接占据候选框第 1、2、3 位供数字键挑选！
- **🧩 丰富的前缀指令系统**：
  - **`call:`**：将拼音还原为提问，直接输出答案本身（如 `call:1+1dengyujivv` $\rightarrow$ `2`）；
  - **`eng:`**：将拼音还原为中文后直译为英语（如 `eng:woshizhongguorenvv` $\rightarrow$ `I am Chinese.`）；
  - **`jp:`**：将拼音还原为中文后直译为日语（如 `jp:woshizhongguorenvv` $\rightarrow$ `私は中国人です。`）；
  - **`cmd:`**：将拼音还原为需求，输出直接可运行的 Windows 命令行；
  - **`sh:`**：将拼音还原为需求，输出 Shell/终端脚本；
  - **`moe:`**：将输出结果改写为软萌可爱的猫娘语气。
- **🔄 全角半角智能兼容**：输入 `call:` 或 `call：` 均能自适应匹配，中文模式下敲 `Shift + ;` 绝不断流。
- **🚀 本地双级极速缓存**：内置 500 条内存 LRU 缓存，输入过的句子再次敲击仅需 **~30ms** 瞬间上屏；联网推理平均只需 **~500ms**。
- **📦 一键安装与纯净卸载**：提供全自动化批处理脚本，双击即可搞定环境部署或无残留还原。

---

## 💻 快速安装

### 前置条件
1. 系统为 Windows 10 / 11；
2. 已安装 [小狼毫 (Weasel)](https://github.com/rime/weasel) 输入法；
3. 如果下载的是 **[独立免安装版 (Release)](https://github.com/mhdy2233/rime-llm-translator-windows/releases/latest)**，**无需系统预装 Python**（内置运行环境）；若克隆源码运行则需 [Python 3.8+](https://www.python.org/)；
4. 拥有一个 [DeepSeek API Key](https://platform.deepseek.com/)（也可通过配置切换为其他兼容 OpenAI 接口的模型）。

### 一键部署
1. 下载本项目源码或 Release 压缩包并解压；
2. 双击运行 **`install.bat`**；
3. 脚本会自动弹出记事本，请将你的 API Key 填入 `api_key` 并保存关闭；
4. 脚本将自动完成配置补丁写入、小狼毫重新部署并静默启动后台服务。

---

## ⌨️ 常用指令与体验

在任何输入框中正常键入拼音，末尾双击 **`vv`** 即可唤醒 AI：

| 指令前缀 | 输入示例 | 输出效果 |
| :--- | :--- | :--- |
| **（无前缀）** | `jinwsncanshendianvv` *(含邻键错拼)* | 候选 1、2、3 分别展示不同可能性的纠正中文长句 |
| **`call:`** | `call:1+1dengyujivv` | 候选首位直接呈现答案：`2` 〔DeepSeek·问答〕 |
| **`eng:`** | `eng:woshizhongguorenvv` | 候选首位输出：`I am Chinese.` 〔DeepSeek·英语〕 |
| **`jp:`** | `jp:woshizhongguorenvv` | 候选首位输出：`私は中国人です。` 〔DeepSeek·日语〕 |
| **`cmd:`** | `cmd:chakanmuluwenjianvv` | 候选首位输出：`dir` 〔DeepSeek·命令〕 |
| **`moe:`** | `moe:nihaovv` | 候选首位输出：`你好喵~` 〔DeepSeek·猫娘〕 |

---

## ⚙️ 高级配置

配置文件位于：`%APPDATA%\rime-llm-daemon\config.json`

```json
{
    "api_key": "YOUR_API_KEY",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat",
    "trigger_suffix": "vv",
    "temperature": 0.1,
    "max_tokens": 120,
    "timeout_seconds": 5.0,
    "debounce_seconds": 0.8
}
```

- **`trigger_suffix`**：唤醒后缀，默认为 `"vv"`；
- **`model`**：模型名称，可切换为 `"deepseek-reasoner"`（推理模型）等；
- **服务启停控制**：
  - 启动后台服务：运行 `%APPDATA%\rime-llm-daemon\start_daemon.bat`
  - 停止后台服务：运行 `%APPDATA%\rime-llm-daemon\stop_daemon.bat`

---

## 🗑️ 如何干净卸载

双击项目根目录下的 **`uninstall.bat`**：
脚本会自动终止后台守护进程、清空缓存、删除 Lua 插件并重新部署小狼毫，100% 毫无残留地恢复至原始状态。

---

## 📄 开源协议

本项目采用 [MIT 许可证](LICENSE) 开源。再次感谢 [rime-llm-translator](https://github.com/SHORiN-KiWATA/rime-llm-translator) 提供的灵感！
