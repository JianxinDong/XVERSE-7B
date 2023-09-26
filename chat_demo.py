import argparse
import torch
import gradio as gr
import json
from datetime import datetime
from transformers import AutoModelForCausalLM, AutoTokenizer,GenerationConfig

tokenizer, model = None, None
css = """
.message.user{
border-color: #BFB0FA !important;
background: #EEEAFF !important;
}
.message.bot{
border-color: #CDCDCD !important;
background: #F8F8F8 !important;
}
"""

def init_model(args):
    global tokenizer, model
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_path, truncation_side="left", padding_side="left")
    model = AutoModelForCausalLM.from_pretrained(args.model_path, trust_remote_code=True, torch_dtype=torch.bfloat16,
                                                 low_cpu_mem_usage=True, device_map='auto')
    model.generation_config = GenerationConfig.from_pretrained(args.model_path)
    model = model.eval()

def chat(message, history, request: gr.Request):
    global tokenizer, model
    history = history or []
    history.append({"role": "user", "content": message})

    # init
    history.append({"role": "assistant", "content": ""})
    utter_history = []
    for i in range(0, len(history), 2):
        utter_history.append([history[i]["content"], history[i+1]["content"]])

    # chat with stream
    for next_text in model.chat(tokenizer, history[:-1], stream=True):
        utter_history[-1][1] += next_text
        history[-1]["content"] += next_text
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
        yield utter_history, history

    # log
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'{current_time} request_ip:{request.client.host}\nquery: {message}\nhistory: {json.dumps(history, ensure_ascii=False)}\nanswer: {json.dumps(utter_history[-1][1], ensure_ascii=False)}')

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=36000,
                       help="server port")
    parser.add_argument("--title", type=str, default="XVERSE-7B-Chat",
                       help="server title")
    parser.add_argument("--model_path", type=str, default="./VERSE-7B-Chat",
                        help="model path")
    parser.add_argument("--tokenizer_path", type=str, default="./XVERSE-7B-Chat",
                        help="Path to the tokenizer.")
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    args = get_args()
    # 初始化模型
    init_model(args)

    # 构建demo应用
    with gr.Blocks(css=css) as demo:
        gr.Markdown("# <center>{}</center>".format(args.title))
        chatbot = gr.Chatbot(label="Chat history", height=650)
        state = gr.State([])

        with gr.Row():
            text_box = gr.Textbox(label="Message", show_label=False, placeholder="Enter message and press enter")

        with gr.Row():
            submit_btn = gr.Button(value="Send", variant="secondary")
            reset_btn = gr.Button(value="Reset")

        text_box.submit(fn=chat,
                        inputs=[text_box, state],
                        outputs=[chatbot, state],
                        api_name="chat")
        submit_btn.click(fn=chat,
                         inputs=[text_box, state],
                         outputs=[chatbot, state])

        # 用于清空text_box
        def clear_textbox():
            return gr.update(value="")
        text_box.submit(fn=clear_textbox, inputs=None, outputs=[text_box])
        submit_btn.click(fn=clear_textbox, inputs=None, outputs=[text_box])

        # 用于清空页面和重置state
        def reset():
            return None, []
        reset_btn.click(fn=reset, inputs=None, outputs=[chatbot, state])

    demo.queue(concurrency_count=4)
    demo.launch(server_name="0.0.0.0", server_port=args.port)
