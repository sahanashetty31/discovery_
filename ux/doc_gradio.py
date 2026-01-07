import gradio as gr
import requests
import json
from typing import List, Dict, Any
import time
import tempfile

# Configuration - Update these with your API details
API_BASE_URL = "http://localhost:8000"  # Change to your FastAPI server URL

def upload_file(files):
    """Upload PDF files to the FastAPI backend"""
    if not files:
        return None, "Please select PDF files", []
    
    uploaded_files = []
    file_statuses = []
    
    for file in files:
        try:
            # Read file content
            with open(file.name, "rb") as f:
                content = f.read()
            
            # Make POST request to /files/upload
            response = requests.post(
                f"{API_BASE_URL}/files/upload",
                files={"file": (file.name, content, "application/pdf")}
            )
            
            if response.status_code == 200:
                result = response.json()
                uploaded_files.append({
                    "file_id": result["file_id"],
                    "filename": result["filename"],
                    "status": result["status"]
                })
                file_statuses.append(f"✅ {result['filename']} - ID: {result['file_id'][:8]}...")
            else:
                file_statuses.append(f"❌ {file.name}: {response.text}")
                
        except Exception as e:
            file_statuses.append(f"❌ {file.name}: {str(e)}")
    
    status_message = "\n".join(file_statuses)
    return None, status_message, uploaded_files

def chat_with_documents(file_ids: List[str], message: str, chat_history):
    """Send chat request to documents"""
    if not file_ids or not message.strip():
        return chat_history, "Please select files and enter a message", []
    
    try:
        chat_messages = [{"role": "user", "content": message}]
        payload = {"file_ids": file_ids, "messages": chat_messages}
        
        response = requests.post(
            f"{API_BASE_URL}/chat-with-document",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            new_history = chat_history + [[message, result["answer"]]]
            
            sources_html = ""
            for source in result.get("sources", []):
                sources_html += f"""
                <div style="margin-bottom: 10px; padding: 8px; border-left: 3px solid #ddd; background: #f8f9fa;">
                    <strong>{source['filename']} ({source['page']})</strong> 
                    <span style="color: #666; font-size: 0.9em; float: right;">
                        Score: {source['relevance_score']}
                    </span><br>
                    <span style="font-size: 0.9em; color: #555;">{source['excerpt'][:400]}...</span>
                </div>
                """
            return new_history, sources_html
        else:
            return chat_history, f"Error: {response.text}", []
            
    except Exception as e:
        return chat_history, f"Chat error: {str(e)}", []

def refresh_file_list():
    """Get list of uploaded files"""
    try:
        response = requests.get(f"{API_BASE_URL}/files/")
        if response.status_code == 200:
            files = response.json()
            if files:
                file_list = "\n".join([
                    f"• {f['filename']} ({f['status']}) - {f['file_id'][:8]}..."
                    for f in files
                ])
                choices = [(f["filename"][:30] + "..." if len(f["filename"]) > 30 else f["filename"], f["file_id"]) for f in files]
                return file_list, choices, choices
            return "No files found", [], []
        return "Error fetching files", [], []
    except:
        return "Error fetching files", [], []

def download_clean_pdf(file_id):
    """Download clean PDF"""
    try:
        response = requests.get(f"{API_BASE_URL}/files/{file_id}/pdf")
        if response.status_code == 200:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            temp_file.write(response.content)
            temp_file.close()
            return temp_file.name
        return None
    except:
        return None

# Create Gradio interface
with gr.Blocks(
    title="Dwani.ai Document Chat",
    theme=gr.themes.Soft(),
    css="""
    .status-completed { color: #27ae60; }
    .status-processing { color: #f39c12; }
    .status-failed { color: #e74c3c; }
    """
) as demo:
    
    gr.Markdown("""
    # 🚀 Dwani.ai Document Chat Interface
    Upload PDFs, chat with multiple documents, and download clean regenerated PDFs.
    """)
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 📁 Upload PDFs")
            file_upload = gr.File(
                label="Upload PDF Files",
                file_types=[".pdf"],
                file_count="multiple"
            )
            
            status_output = gr.Markdown()
            uploaded_files = gr.State([])
            
            with gr.Row():
                refresh_btn = gr.Button("🔄 Refresh Files", variant="secondary")
                file_list_output = gr.Markdown(value="Click refresh to see uploaded files")
            
            gr.Markdown("### 📋 Select Files for Chat")
            file_checklist = gr.CheckboxGroup(
                label="Available Files",
                choices=[],
                value=[]
            )
        
        with gr.Column(scale=2):
            gr.Markdown("### 💬 Chat with Documents")
            chat_history = gr.Chatbot(height=400)
            msg_input = gr.Textbox(
                placeholder="Ask questions about your uploaded documents...",
                scale=3
            )
            chat_btn = gr.Button("Send", variant="primary")
            
            sources_output = gr.HTML(value="")
            
            gr.Markdown("### ⬇️ Download Clean PDF")
            with gr.Row():
                download_file_id = gr.Dropdown(
                    label="Select file",
                    choices=[],
                    interactive=True
                )
                download_btn = gr.Button("⬇️ Download", variant="secondary")
            download_file = gr.File(label="Clean PDF")
    
    # Events
    file_upload.upload(upload_file, [file_upload], [file_upload, status_output, uploaded_files])
    
    refresh_btn.click(refresh_file_list, outputs=[file_list_output, file_checklist, download_file_id])
    
    chat_btn.click(chat_with_documents, [file_checklist, msg_input, chat_history], [chat_history, sources_output]).then(
        lambda: "", outputs=msg_input
    )
    
    msg_input.submit(chat_with_documents, [file_checklist, msg_input, chat_history], [chat_history, sources_output]).then(
        lambda: "", outputs=msg_input
    )
    
    download_btn.click(download_clean_pdf, [download_file_id], [download_file])

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
        debug=True,
        max_file_size="50MB"  # ✅ File size limit goes HERE
    )
