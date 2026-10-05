-- ==============================================================================
-- rime_llm.lua: 纯后台轻量级 AI 联想与整句翻译扩展（支持 call:/eng:/jp: 等前缀指令）
-- 特性：
--   1. 双击 vv 触发（如输入 nihaoshijievv、call:xianzaijidianvv、eng:woshizhongguorenvv）
--   2. 0 弹黑框（纯文件流与本机 Daemon 握手，无任何进程调用）
--   3. Daemon 未启动时秒级穿透，不影响日常任何正常打字
-- ==============================================================================

local M = {}

local temp_dir = os.getenv("TEMP") or "C:/Users/38776/AppData/Local/Temp"
local ipc_dir = temp_dir:gsub("\\", "/") .. "/rime_llm_ipc"
local status_file = ipc_dir .. "/daemon.status"

function M.init(env)
    math.randomseed(os.time())
    env.commit_history = {}
    local ctx = env.engine and env.engine.context
    if ctx and ctx.commit_notifier then
        env.commit_conn = ctx.commit_notifier:connect(function(c)
            local text = c:get_commit_text()
            if text and #text > 0 and text:match("%S") then
                table.insert(env.commit_history, text)
                local total_len = 0
                for _, s in ipairs(env.commit_history) do
                    total_len = total_len + #s
                end
                while #env.commit_history > 1 and total_len > 240 do
                    local removed = table.remove(env.commit_history, 1)
                    total_len = total_len - #removed
                end
            end
        end)
    end
end

function M.fini(env)
    if env and env.commit_conn then
        env.commit_conn:disconnect()
        env.commit_conn = nil
    end
end

local function parse_json_field(json_str, field)
    if not json_str or json_str == "" then return nil end
    local val = json_str:match('"' .. field .. '"%s*:%s*"(.-)"%s*[,}]')
    if val then
        val = val:gsub('\\"', '"'):gsub('\\n', ' '):gsub('\\\\', '\\')
        return val
    end
    return nil
end

local function parse_json_results(json_str)
    if not json_str or json_str == "" then return {} end
    local arr_str = json_str:match('"results"%s*:%s*%[(.-)%]')
    local list = {}
    if arr_str then
        for item in arr_str:gmatch('"(.-)"') do
            item = item:gsub('\\"', '"'):gsub('\\n', ' '):gsub('\\\\', '\\')
            if #item > 0 then
                list[#list + 1] = item
            end
        end
    end
    if #list == 0 then
        local single = json_str:match('"result"%s*:%s*"(.-)"%s*[,}]')
        if single then
            single = single:gsub('\\"', '"'):gsub('\\n', ' '):gsub('\\\\', '\\')
            list[1] = single
        end
    end
    return list
end

function M.func(input, seg, env)
    local ctx_input = env.engine.context.input
    local dbg = io.open(ipc_dir .. "/lua_debug.log", "a")
    if dbg then
        dbg:write(string.format("[%s] seg_input='%s', ctx_input='%s', start=%d, end=%d\n", os.date("%H:%M:%S"), tostring(input), tostring(ctx_input), seg.start, seg._end))
        dbg:close()
    end
    -- 优先获取整句输入缓冲区（避免被分词器切碎导致无法匹配 vv）
    local ctx = env.engine.context
    local raw_str = (ctx and ctx.input) or input
    if not raw_str or #raw_str < 3 then return end
    if raw_str:sub(-2) ~= "vv" then return end

    -- 若被分成了多个 segment，仅在首个 segment 处理以覆盖整段输入，避免重复派发
    if seg.start > 0 and ctx and ctx.input and ctx.input:sub(-2) == "vv" then
        return
    end

    local pinyin = raw_str:sub(1, -3)
    -- 校验：不能包含空白，且必须包含有效内容
    if #pinyin == 0 or pinyin:match("%s") then return end

    -- 检查守护进程状态
    local sf = io.open(status_file, "r")
    if not sf then
        local tip = Candidate("llm", seg.start, seg._end, "请先启动 rime-llm-daemon 后台服务", "〔AI未连接〕")
        tip.quality = 1000000
        yield(tip)
        return
    end
    sf:close()

    -- 构造请求
    local req_id = tostring(os.time()) .. "_" .. tostring(math.random(10000, 99999))
    local req_path = ipc_dir .. "/req_" .. req_id .. ".json"
    local tmp_path = req_path .. ".tmp"
    local resp_path = ipc_dir .. "/resp_" .. req_id .. ".json"

    local f_req = io.open(tmp_path, "w")
    if not f_req then return end
    local context_text = ""
    if env and env.commit_history and #env.commit_history > 0 then
        context_text = table.concat(env.commit_history, "")
        if #context_text > 180 then
            context_text = context_text:sub(-180)
        end
    end

    local safe_py = pinyin:gsub('\\', '\\\\'):gsub('"', '\\"')
    local safe_ctx = context_text:gsub('\\', '\\\\'):gsub('"', '\\"')
    f_req:write(string.format('{"id": "%s", "pinyin": "%s", "context": "%s"}', req_id, safe_py, safe_ctx))
    f_req:close()
    os.rename(tmp_path, req_path)

    -- 轮询等待响应 (硬上限 3.5 秒)
    local max_wait = 3.5
    local start_clock = os.clock()
    local resp_data = nil

    while (os.clock() - start_clock) < max_wait do
        local f_resp = io.open(resp_path, "r")
        if f_resp then
            resp_data = f_resp:read("*a")
            f_resp:close()
            pcall(os.remove, resp_path)
            break
        end

        -- 极小非阻塞休眠 15ms 节约 CPU
        local t0 = os.clock()
        while (os.clock() - t0) < 0.015 do end
    end

    if resp_data then
        local results = parse_json_results(resp_data)
        local tag = parse_json_field(resp_data, "tag")
        local base_comment = "〔DeepSeek〕"
        if tag and tag ~= "" then
            base_comment = "〔DeepSeek·" .. tag .. "〕"
        end

        if #results > 0 then
            local c_start = (ctx and ctx.input and ctx.input:sub(-2) == "vv") and 0 or seg.start
            local c_end = (ctx and ctx.input and ctx.input:sub(-2) == "vv") and #ctx.input or seg._end
            for i, text in ipairs(results) do
                local cand = Candidate("llm", c_start, c_end, text, base_comment)
                cand.quality = 1000000 - (i - 1) * 10
                cand.preedit = pinyin .. " "
                yield(cand)
            end
            return
        end
    end

    -- 超时或无响应提示
    local err_cand = Candidate("llm", seg.start, seg._end, "AI 响应超时，请重试", "〔超时〕")
    err_cand.quality = 1000000
    yield(err_cand)
end

return M
