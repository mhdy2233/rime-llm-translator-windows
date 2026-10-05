#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rime-llm-daemon: 纯后台轻量级 Rime AI 联想守护进程
0 外部库依赖，使用 Python 标准库实现双级缓存与零黑框文件 IPC 通信。
"""

import os
import sys
import json
import time
import glob
import urllib.request
import urllib.error
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "api_key": "",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "trigger_suffix": "vv",
        "temperature": 0.1,
        "max_tokens": 500,
        "enable_context": False,
        "max_context_length": 60,
        "timeout_seconds": 5.0,
        "ipc_dir": os.path.join(os.environ.get("TEMP", "C:/Temp"), "rime_llm_ipc"),
        "system_prompt": "你是一个智能拼音输入法AI联想引擎。将用户的长拼音转换为自然、通顺、合理的中文句子。允许纠错、纠音、混合中英文。直接输出最终上屏句子，严禁包含任何客套话、解释说明或Markdown格式。"
    }

LOG_FILE = None
def log(msg):
    global LOG_FILE
    if LOG_FILE:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        except Exception:
            pass

MEM_CACHE = {}

PREFIX_RULES = {
    "call": {
        "tag": "问答",
        "prompt": "不要输出拼音转换的结果。把用户输入的拼音还原出的句子当作向你提出的问题，直接输出答案本身，精炼准确，不说废话，严禁包含任何客套话、解释说明或Markdown代码块。"
    },
    "eng": {
        "tag": "英语",
        "prompt": "你是一个智能拼音翻译引擎。把用户输入的拼音先还原为中文含义，然后只输出对应的英文译文。严禁输出中间的中文，不要附带原文，严禁包含任何解释说明或Markdown格式。"
    },
    "jp": {
        "tag": "日语",
        "prompt": "你是一个智能拼音翻译引擎。把用户输入的拼音先还原为中文含义，然后只输出对应的日文译文。严禁输出中间的中文，不要附带原文，严禁包含任何解释说明或Markdown格式。"
    },
    "cmd": {
        "tag": "命令",
        "prompt": "不要输出拼音转换的结果。把用户拼音还原出的需求，只输出可直接在当前系统终端中运行的命令行指令本身，前后不许有任何解释、说明或代码块标记。"
    },
    "sh": {
        "tag": "脚本",
        "prompt": "不要输出拼音转换的结果。把用户拼音还原出的需求，只输出终端脚本正文，不要用Markdown代码块包裹，不要任何解释。"
    },
    "moe": {
        "tag": "猫娘",
        "prompt": "你是一个智能拼音输入法引擎。把用户的拼音转换为自然、通顺的句子，并改写成可爱的猫娘语气和用词（句末带喵等），只输出改写后的最终结果，不要任何解释说明。"
    }
}

def call_deepseek_api(cfg, pinyin_input, context=""):
    clean_pinyin = pinyin_input.strip().replace("：", ":")
    clean_context = context.strip() if context else ""
    enable_context = cfg.get("enable_context", True)
    max_ctx_len = cfg.get("max_context_length", 60)
    if clean_context and len(clean_context) > max_ctx_len:
        clean_context = clean_context[-max_ctx_len:]

    prefix = None
    body = clean_pinyin
    tag = ""
    system_prompt = (
        "你是专业中文拼音输入法AI联想引擎。将用户的长拼音转换为自然、通顺、符合日常口语与书面语境的句子。\n"
        "用户输入极可能包含打字失误，请充分推理其真实意图并进行智能容错：\n"
        "1. 键盘邻键物理误触（如 a/s/w 互串、i/o/p 互串、g/h 互串等）；\n"
        "2. 漏打字母或简拼音节（如 rn->ren、shij->shijie）；\n"
        "3. 前后鼻音混淆（如 in/ing、en/eng、an/ang）。\n"
        "输出要求：\n"
        "请按概率从高到低提供最多 3 个【互不相同、各具差异】的候选句子，每行一个（按第1到第3行输出）：\n"
        "- 第1行（首选）：最符合标准汉语语境、最通顺自然的高概率整句；\n"
        "- 第2行（次选）：语义合理但词界切分或同音字用词不同的备选句子；\n"
        "- 第3行（容错）：考虑可能存在键盘误触或拼写失误后的强纠错句子。\n"
        "严格规则：\n"
        "- 绝对禁止输出完全相同的重复句子，3个候选必须各不相同；\n"
        "- 严禁输出任何序号（不要1. 2. 3.）、拼音、解释说明或额外标点。"
    )

    if ":" in clean_pinyin:
        p_prefix, p_body = clean_pinyin.split(":", 1)
        p_key = p_prefix.strip().lower()
        if p_key in PREFIX_RULES:
            prefix = p_key
            body = p_body.strip()
            tag = PREFIX_RULES[p_key]["tag"]
            system_prompt = PREFIX_RULES[p_key]["prompt"]

    use_context = bool(enable_context and clean_context and not prefix)
    cache_key = f"ctx:{clean_context}:{clean_pinyin}" if use_context else clean_pinyin
    if cache_key in MEM_CACHE:
        cached_res, tag = MEM_CACHE[cache_key]
        return cached_res, True, tag

    if use_context:
        user_content = f"【前文参考】：{clean_context}\n【当前输入拼音】：{body}"
        system_prompt += "\n重要：若提供了【前文参考】，请务必结合前文语义进行上下文消歧与连贯推测（例如前文提到汽车时，当前拼音 youxiang 应当为油箱而非邮箱）。"
    else:
        user_content = body

    url = f"{cfg.get('base_url', 'https://api.deepseek.com').rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg.get('api_key', '')}",
        "User-Agent": "Rime-LLM-Daemon/1.0"
    }
    payload = {
        "model": cfg.get("model", "deepseek-chat"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.4 if not prefix else cfg.get("temperature", 0.1),
        "max_tokens": cfg.get("max_tokens", 500)
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=cfg.get("timeout_seconds", 5.0)) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_content = data["choices"][0]["message"]["content"].strip()

            results = []
            if prefix:
                content = raw_content.replace("\n", " ").strip()
                if content.startswith('"') and content.endswith('"'):
                    content = content[1:-1].strip()
                if content.startswith('“') and content.endswith('”'):
                    content = content[1:-1].strip()
                if content:
                    results = [content]
            else:
                for line in raw_content.splitlines():
                    line = line.strip()
                    line = re.sub(r"^[\d一二三四五六七八九十]+[.\、\s\-]+", "", line).strip()
                    if line.startswith('"') and line.endswith('"'):
                        line = line[1:-1].strip()
                    if line.startswith('“') and line.endswith('”'):
                        line = line[1:-1].strip()
                    if line and line not in results:
                        results.append(line)
                if not results and raw_content:
                    results = [raw_content.replace("\n", " ").strip()]
                results = results[:3]

            MEM_CACHE[cache_key] = (results, tag)
            if len(MEM_CACHE) > 500:
                oldest = next(iter(MEM_CACHE))
                MEM_CACHE.pop(oldest, None)

            dt = (time.time() - t0) * 1000
            tag_info = f"[{tag}] " if tag else ""
            ctx_info = f"[前文:{clean_context}] " if use_context else ""
            log(f"DeepSeek 返回成功: {tag_info}{ctx_info}{clean_pinyin} -> {results} ({dt:.0f}ms)")
            return results, False, tag
    except Exception as e:
        err_msg = f"[AI错误: {e}]"
        log(f"DeepSeek 调用失败: {err_msg}")
        return [err_msg], False, tag

def call_deepseek_rerank(cfg, context, pinyin, candidates):
    if not context or not candidates:
        return candidates[0] if candidates else "", True
    cache_key = f"rerank:{context}:{pinyin}:{','.join(candidates)}"
    if cache_key in MEM_CACHE:
        return MEM_CACHE[cache_key], True
    url = f"{cfg.get('base_url', 'https://api.deepseek.com').rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg.get('api_key', '')}",
        "User-Agent": "Rime-LLM-Daemon/1.0"
    }
    options_str = "、".join(candidates)
    system_msg = "你是一个输入法上下文决策引擎。根据前文语境，从给出的候选词列表中选出最自然、最契合当前语境的一个词。只直接输出该词本身，严禁包含任何序号、解释或额外字符。"
    user_msg = f"前文语境：{context}\\n候选词列表：{options_str}"
    payload = {
        "model": cfg.get("model", "deepseek-chat"),
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ],
        "temperature": 0.0,
        "max_tokens": 16
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=cfg.get("timeout_seconds", 5.0)) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"].strip()
            for q in ['"', "'", "“", "”", "‘", "’", "`"]:
                content = content.replace(q, '')
            content = content.strip()
            chosen = None
            for cand in candidates:
                if cand == content or cand in content:
                    chosen = cand
                    break
            if not chosen:
                chosen = candidates[0]
            MEM_CACHE[cache_key] = chosen
            dt = (time.time() - t0) * 1000
            log(f"Rerank 成功: [{context}] + {pinyin} -> {chosen} (从 {candidates} 选出, 耗时 {dt:.0f}ms)")
            return chosen, False
    except Exception as e:
        err_msg = f"[Rerank错误: {e}]"
        log(f"Rerank 失败: {err_msg}")
        return candidates[0], False

def run_loop():
    global LOG_FILE
    cfg = load_config()
    ipc_dir = cfg.get("ipc_dir", os.path.join(os.environ.get("TEMP", "C:/Temp"), "rime_llm_ipc"))
    os.makedirs(ipc_dir, exist_ok=True)
    LOG_FILE = os.path.join(ipc_dir, "daemon.log")
    
    log(f"守护进程启动 (PID: {os.getpid()})")
    if cfg.get("enable_context", False):
        log("⚠️ 隐私警告：当前已开启上下文联想 (enable_context=true)，上屏历史文字将被发送至云端 AI，请注意隐私安全！")
    else:
        log("隐私安全：上下文联想已默认关闭 (enable_context=false)，不收集上屏历史文字。")
    status_file = os.path.join(ipc_dir, "daemon.status")
    with open(status_file, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))

    try:
        pending_rerank = None
        while True:
            req_files = glob.glob(os.path.join(ipc_dir, "req_*.json"))
            for rf in req_files:
                if rf.endswith(".tmp"):
                    continue
                req_data = None
                try:
                    with open(rf, "r", encoding="utf-8-sig") as f:
                        content = f.read().strip()
                        # 兼容 powershell 误带转义引号的情况
                        if content.startswith('"') and content.endswith('"') and '\\"' in content:
                            content = content[1:-1].replace('\\"', '"')
                        req_data = json.loads(content)
                except (json.JSONDecodeError, PermissionError, OSError) as e:
                    # 如果重试多次依然出错，记录并清理
                    log(f"解析请求失败 {rf}: {e}")
                    try:
                        os.remove(rf)
                    except OSError:
                        pass
                    continue
                
                if req_data and isinstance(req_data, dict):
                    req_id = req_data.get("id")
                    pinyin = req_data.get("pinyin", "")
                    
                    if req_id and pinyin:
                        req_type = req_data.get("type", "translate")
                        if req_type == "rerank":
                            context = req_data.get("context", "")
                            cands = req_data.get("candidates", [])
                            if pending_rerank:
                                log(f"去抖拦截：800ms 内有新按键，取消旧请求 id={pending_rerank['id']} ({pending_rerank['pinyin']})")
                            pending_rerank = {
                                "id": req_id,
                                "context": context,
                                "pinyin": pinyin,
                                "candidates": cands,
                                "time": time.time()
                            }
                        else:
                            log(f"接收翻译请求: id={req_id}, pinyin={pinyin}")
                            context_in = req_data.get("context", "")
                            results, cached, tag = call_deepseek_api(cfg, pinyin, context=context_in)
                            first_result = results[0] if results else ""
                            resp_file = os.path.join(ipc_dir, f"resp_{req_id}.json")
                            tmp_resp = resp_file + ".tmp"
                            try:
                                with open(tmp_resp, "w", encoding="utf-8") as f:
                                    json.dump({
                                        "id": req_id,
                                        "type": "translate",
                                        "pinyin": pinyin,
                                        "result": first_result,
                                        "results": results,
                                        "tag": tag,
                                        "cached": cached,
                                        "time": time.time()
                                    }, f, ensure_ascii=False)
                                os.replace(tmp_resp, resp_file)
                                log(f"写入响应完成: {resp_file}")
                            except Exception as e:
                                log(f"写入响应异常: {e}")
                    try:
                        os.remove(rf)
                    except OSError:
                        pass

            # 检查静止超过 800ms 的 Rerank 待决请求
            if pending_rerank and (time.time() - pending_rerank["time"]) >= cfg.get("debounce_seconds", 0.800):
                r_id = pending_rerank["id"]
                r_ctx = pending_rerank["context"]
                r_py = pending_rerank["pinyin"]
                r_cands = pending_rerank["candidates"]
                pending_rerank = None
                log(f"静止超过 800ms，触发 DeepSeek Rerank: id={r_id}, context={r_ctx}, pinyin={r_py}")
                chosen, cached = call_deepseek_rerank(cfg, r_ctx, r_py, r_cands)
                resp_file = os.path.join(ipc_dir, f"resp_{r_id}.json")
                tmp_resp = resp_file + ".tmp"
                try:
                    with open(tmp_resp, "w", encoding="utf-8") as f:
                        json.dump({
                            "id": r_id,
                            "type": "rerank",
                            "selected": chosen,
                            "cached": cached,
                            "time": time.time()
                        }, f, ensure_ascii=False)
                    os.replace(tmp_resp, resp_file)
                    log(f"写入 Rerank 响应完成: {resp_file}")
                except Exception as e:
                    log(f"写入 Rerank 响应异常: {e}")
            time.sleep(0.015)
    except KeyboardInterrupt:
        log("守护进程退出")
    finally:
        if os.path.exists(status_file):
            try:
                os.remove(status_file)
            except OSError:
                pass

def stop_daemon():
    cfg = load_config()
    ipc_dir = cfg.get("ipc_dir", os.path.join(os.environ.get("TEMP", "C:/Temp"), "rime_llm_ipc"))
    status_file = os.path.join(ipc_dir, "daemon.status")
    if os.path.exists(status_file):
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                pid = int(f.read().strip())
            os.system(f"taskkill /F /PID {pid} >nul 2>&1")
            print(f"[OK] 已停止 rime-llm-daemon (PID: {pid})")
        except Exception as e:
            print(f"[WARN] 停止异常: {e}")
        try:
            os.remove(status_file)
        except OSError:
            pass
    else:
        print("[INFO] 守护进程未在运行。")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_input = sys.argv[2] if len(sys.argv) > 2 else "nihaoshijie"
        print(f"正在测试 DeepSeek 联通性，输入拼音: {test_input} ...")
        t0 = time.time()
        cfg = load_config()
        out, cached = call_deepseek_api(cfg, test_input)
        dt = (time.time() - t0) * 1000
        print(f"转换结果: {out}")
        print(f"耗时: {dt:.1f} ms | 缓存命中: {cached}")
    elif len(sys.argv) > 1 and sys.argv[1] == "stop":
        stop_daemon()
    elif len(sys.argv) > 1 and sys.argv[1] == "test-rerank":
        ctx = sys.argv[2] if len(sys.argv) > 2 else "汽车"
        py = sys.argv[3] if len(sys.argv) > 3 else "youxiang"
        cands = sys.argv[4].split(",") if len(sys.argv) > 4 else ["邮箱", "又想", "油箱", "幽香"]
        print(f"正在测试 Rerank 决策，前文语境: '{ctx}'，输入拼音: '{py}'，候选: {cands} ...")
        t0 = time.time()
        cfg = load_config()
        chosen, cached = call_deepseek_rerank(cfg, ctx, py, cands)
        dt = (time.time() - t0) * 1000
        print(f"DeepSeek 决策选出: 【{chosen}】")
        print(f"耗时: {dt:.1f} ms | 缓存命中: {cached}")
    else:
        run_loop()
