"""Prompt locally; credentials remain in this process, never in project files."""
import getpass
import os
import runpy
from pathlib import Path

if __name__ == "__main__":
    key = getpass.getpass("OpenAI API key（隐藏输入，不保存到文件）: ").strip()
    if not key:
        raise SystemExit("未输入密钥，未启动模型服务。离线预览可运行 python3 server.py。")
    model = input("模型 ID [gpt-4.1-mini]: ").strip() or "gpt-4.1-mini"
    os.environ["OPENAI_API_KEY"] = key
    os.environ["OPENAI_MODEL"] = model
    print("启动仅限本机的预览。点击 AI 功能才会请求模型并产生 API 用量。")
    try:
        runpy.run_path(str(Path(__file__).with_name("server.py")), run_name="__main__")
    except OSError as exc:
        if exc.errno == 48 or exc.errno == 98:
            raise SystemExit("8767 端口已被占用。请在原预览终端按 Ctrl+C 停止旧服务，然后重试。") from None
        raise
