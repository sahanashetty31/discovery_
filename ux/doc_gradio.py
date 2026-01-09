"""
Dwani.ai Gradio UI - Multiple File Upload + Chat Display PERFECTED
"""

import gradio as gr
import requests
from typing import List, Dict
from datetime import datetime
import time

API_BASE = "http://localhost:8000"

class DwaniClient:
    def __init__(self, base_url=API_BASE):
        self.base_url = base_url.rstrip('/')
    
    def upload_file(self, file_path: str) -> dict:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            resp = requests.post(f"{self.base_url}/files/upload", files=files)
            resp.raise_for_status()
            return resp.json()
    
    def get_file_status(self, file_id: str) -> dict:
        resp = requests.get(f"{self.base_url}/files/{file_id}")
        resp.raise_for_status()
        return resp.json()
    
    def list_files(self) -> List[dict]:
        resp = requests.get(f"{self.base_url}/files/")
        resp.raise_for_status()
        return resp.json()
    
    def chat(self, file_ids: List[str], messages: List[Dict]) -> dict:
        payload = {"file_ids": file_ids, "messages": messages}
        resp = requests.post(f"{self.base_url}/chat-with-document", json=payload)
        resp.raise_for_status()
        return resp.json()

client = DwaniClient()
uploaded_files = {}
chat_history: List[Dict] = []
selected_files = []

def poll_file_status(file_id: str, max_wait=60):
    """Wait for file processing"""
    for _ in range(max_wait):
        try:
            status = client.get_file_status(file_id)
            if status['status'] == 'completed': return status, True
            if status['status'] == 'failed': return status, False
            time.sleep(2)
        except: time.sleep(2)
    return {'status': 'timeout'}, False

def upload_multiple(files):
    """Handle multiple PDF uploads"""
    if not files:
        return "No files selected", gr.update(choices=[])
    
    global uploaded_files
    status_msgs = []
    
    for file in files:
        try:
            # Upload each file
            result = client.upload_file(file.name)
            file_id = result['file_id']
            filename = result['filename']
            
            uploaded_files[file_id] = {
                'filename': filename, 
                'status': 'pending',
                'file_id': file_id
            }
            
            # Poll for completion
            status, success = poll_file_status(file_id)
            
            if success:
                uploaded_files[file_id]['status'] = 'completed'
                status_msgs.append(f"✅ {filename} - READY")
            else:
                uploaded_files[file_id]['status'] = 'failed'
                status_msgs.append(f"❌ {filename} - FAILED")
                
        except Exception as e:
            status_msgs.append(f"❌ {file.name} - ERROR: {str(e)}")
    
    # Update choices for only completed files
    choices = [(info['filename'], info['file_id']) for info in uploaded_files.values() 
               if info['status'] == 'completed']
    
    return "\n".join(status_msgs), gr.update(choices=choices), create_file_list()

def refresh_files():
    """Refresh from server"""
    try:
        files = client.list_files()
        global uploaded_files
        uploaded_files.clear()
        
        for f in files:
            uploaded_files[f['file_id']] = f
        
        choices = [(f['filename'], f['file_id']) for f in files if f['status'] == 'completed']
        return create_file_list(), gr.update(choices=choices)
    except:
        return "Refresh failed", gr.update()

def create_file_list():
    """Display all files with status"""
    if not uploaded_files:
        return "No files uploaded"
    
    lines = ["**📁 Your Files:**"]
    for info in uploaded_files.values():
        emoji = {
            'completed': '✅', 
            'processing': '🔄', 
            'pending': '⏳', 
            'failed': '❌'
        }.get(info['status'], '❓')
        lines.append(f"{emoji} {info['filename']} ({info['status']})")
    return "\n".join(lines)

def update_selected_files(files):
    """Update selected files"""
    global selected_files
    selected_files = files or []
    return len(selected_files)

def send_message(message, history):
    """Send chat message - FIXED DISPLAY"""
    global chat_history, selected_files
    
    if not message.strip():
        return history, ""
    
    if not selected_files:
        return history, "⚠️ Please select files first!"
    
    # Create new history entry for user
    user_message = {"role": "user", "content": message}
    assistant_message = {"role": "assistant", "content": "Thinking..."}
    
    # Update UI immediately
    new_history = history + [user_message, assistant_message]
    
    try:
        # Prepare full conversation for API
        api_messages = chat_history + [user_message]
        
        # Call backend
        result = client.chat(selected_files, api_messages)
        
        # Update chat history with real response
        chat_history.append(user_message)
        chat_history.append({"role": "assistant", "content": result['answer']})
        
        # Format beautiful response with sources
        full_response = format_chat_response(result)
        
        # Replace "Thinking..." with real answer
        final_history = history + [user_message, {"role": "assistant", "content": full_response}]
        return final_history, ""
        
    except Exception as e:
        error_response = {"role": "assistant", "content": f"❌ Error: {str(e)}"}
        return new_history[:-1] + [error_response], f"Error: {str(e)}"

def format_chat_response(result):
    """Format response with sources"""
    answer = result['answer']
    
    if result.get('sources'):
        sources = "\n\n**📚 Sources:**\n"
        for i, src in enumerate(result['sources'][:5], 1):
            sources += f"{i}. **{src['filename']}** (Page {src['page']})\n"
            sources += f"   > {src['excerpt'][:120]}...\n\n"
        return answer + sources
    return answer

def clear_chat():
    """Clear conversation"""
    global chat_history
    chat_history = []
    return []

# === UI LAYOUT ===
with gr.Blocks(title="Dwani.ai", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 📚 Dwani.ai - Document Chat")
    gr.Markdown("**Upload multiple PDFs → Chat with page-accurate citations**")
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## 📤 Upload Multiple PDFs")
            file_input = gr.File(
                label="Select PDFs (Ctrl+Click for multiple)", 
                file_types=[".pdf"],
                file_count="multiple"  # ✅ MULTIPLE FILES SUPPORT
            )
            upload_btn = gr.Button("🚀 Upload & Process All", variant="primary")
            
            status_output = gr.Markdown("Ready to upload...")
            refresh_btn = gr.Button("🔄 Refresh List")
            files_display = gr.Markdown("No files uploaded")
        
        with gr.Column(scale=2):
            gr.Markdown("## 📋 File Manager")
            file_checkboxes = gr.CheckboxGroup(
                label="Select documents to chat with:",
                choices=[],
                value=[],
                info="Only completed files appear here"
            )
            file_count = gr.Number(label="Files selected", value=0, interactive=False)
    
    with gr.Row():
        gr.Markdown("## 💬 Chat with Documents")
        chatbot = gr.Chatbot(
            label="Ask questions about your documents",
            height=500,
            avatar_images=("user.png", "assistant.png")
        )
    
    with gr.Row():
        msg_input = gr.Textbox(
            label="Your question",
            placeholder="e.g., What are the payment terms? When does the contract expire?",
            scale=4
        )
        send_btn = gr.Button("Send", variant="primary", scale=1)
    
    with gr.Row():
        clear_btn = gr.Button("🗑️ New Chat", variant="secondary")
    
    # Event connections
    upload_btn.click(
        upload_multiple,
        inputs=file_input,
        outputs=[status_output, file_checkboxes, files_display]
    )
    
    refresh_btn.click(
        refresh_files,
        outputs=[files_display, file_checkboxes]
    )
    
    file_checkboxes.change(
        update_selected_files,
        inputs=file_checkboxes,
        outputs=file_count
    )
    
    send_btn.click(
        send_message,
        inputs=[msg_input, chatbot],
        outputs=[chatbot, msg_input]
    )
    
    msg_input.submit(
        send_message,
        inputs=[msg_input, chatbot],
        outputs=[chatbot, msg_input]
    )
    
    clear_btn.click(
        clear_chat,
        outputs=chatbot
    )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
        debug=True
    )
