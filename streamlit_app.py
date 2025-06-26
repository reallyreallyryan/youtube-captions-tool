import streamlit as st
import os
import tempfile
import subprocess
import time
from openai import OpenAI
from pathlib import Path
import pandas as pd

# Page config
st.set_page_config(
    page_title="🎬 Jasper Caption Generator",
    page_icon="🎬",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
        color: white;
    }
    .success-box {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .error-box {
        background: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

class YouTubeCaptionGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    def process_shorts_url(self, youtube_url):
        """Process YouTube Shorts URL and return caption"""
        try:
            st.info(f"🎥 Processing: {youtube_url}")
            
            # Validate URL
            if 'youtube.com/shorts/' not in youtube_url and 'youtu.be/' not in youtube_url:
                return {'success': False, 'error': 'Invalid YouTube URL'}
            
            # Extract transcript
            transcript = self._extract_transcript(youtube_url)
            if not transcript:
                return {'success': False, 'error': 'Could not extract transcript'}
            
            # Generate caption
            caption = self._generate_caption(transcript)
            
            return {
                'success': True,
                'caption': caption,
                'transcript': transcript[:200] + '...' if len(transcript) > 200 else transcript
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _extract_transcript(self, youtube_url):
        """Extract transcript from YouTube video"""
        # Try auto-transcript first
        transcript = self._get_auto_transcript(youtube_url)
        if transcript:
            st.success("✅ Found auto-transcript!")
            return transcript
        
        st.warning("❌ No auto-transcript found, downloading audio...")
        
        # Fallback: Download audio and transcribe
        audio_path = self._download_audio(youtube_url)
        if audio_path:
            transcript = self._transcribe_audio(audio_path)
            if os.path.exists(audio_path):
                os.unlink(audio_path)
            return transcript
        
        return None
    
    def _get_auto_transcript(self, youtube_url):
        """Try to extract auto-generated captions"""
        try:
            cmd = [
                'yt-dlp', '--write-auto-subs', '--write-subs', '--skip-download',
                '--sub-format', 'vtt', '--sub-langs', 'en', youtube_url
            ]
            
            with tempfile.TemporaryDirectory() as temp_dir:
                result = subprocess.run(cmd, cwd=temp_dir, capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    vtt_files = list(Path(temp_dir).glob('*.vtt'))
                    if vtt_files:
                        with open(vtt_files[0], 'r', encoding='utf-8') as f:
                            vtt_content = f.read()
                        
                        # Extract text from VTT
                        lines = vtt_content.split('\n')
                        transcript_lines = []
                        
                        for line in lines:
                            line = line.strip()
                            if line and not line.startswith('WEBVTT') and '-->' not in line and not line.isdigit():
                                transcript_lines.append(line)
                        
                        return ' '.join(transcript_lines)
        except:
            pass
        
        return None
    
    def _download_audio(self, youtube_url):
        """Download audio from YouTube video"""
        try:
            st.info("🎵 Downloading audio...")
            
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_path = temp_file.name
            
            cmd = [
                'yt-dlp', '-x', '--audio-format', 'mp3',
                '--audio-quality', '0',
                '-o', temp_path.replace('.mp3', '.%(ext)s'),
                youtube_url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                possible_files = [
                    temp_path,
                    temp_path.replace('.mp3', '.m4a'),
                    temp_path.replace('.mp3', '.webm')
                ]
                
                for file_path in possible_files:
                    if os.path.exists(file_path):
                        st.success(f"✅ Audio downloaded: {os.path.basename(file_path)}")
                        return file_path
                
                st.error("❌ No audio file found despite success")
                return None
            else:
                st.error(f"❌ Audio download failed (code {result.returncode})")
                if result.stderr:
                    st.error(f"Error: {result.stderr[:200]}...")
                return None
                
        except subprocess.TimeoutExpired:
            st.error("⏰ Audio download timed out")
            return None
        except Exception as e:
            st.error(f"💥 Audio download failed: {str(e)}")
            return None
    
    def _transcribe_audio(self, audio_path):
        """Transcribe audio using OpenAI Whisper"""
        try:
            st.info("🎤 Transcribing audio with Whisper...")
            
            # Check file exists and size
            if not os.path.exists(audio_path):
                st.error("❌ Audio file doesn't exist")
                return None
                
            file_size = os.path.getsize(audio_path)
            st.info(f"📁 Audio file size: {file_size} bytes")
            
            if file_size == 0:
                st.error("❌ Audio file is empty")
                return None
            
            with open(audio_path, 'rb') as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
            
            st.success(f"✅ Transcription complete: {len(transcript)} chars")
            return transcript
            
        except Exception as e:
            st.error(f"💥 Whisper transcription failed: {str(e)}")
            return None
    
    def _generate_caption(self, transcript):
        """Generate caption from transcript"""
        if not transcript:
            return "❌ No transcript available"
        
        st.info("✨ Generating caption with AI...")
        
        prompt = f"""
You are a social media expert specializing in healthcare marketing. 

Create a catchy, engaging caption for a YouTube Short based on this transcript.

TRANSCRIPT:
{transcript}

REQUIREMENTS:
- 1-2 punchy sentences maximum
- Healthcare/medical tone but accessible to general audience  
- Include relevant emojis (2-3 max)
- Focus on the key insight or takeaway
- Make it shareable and engaging
- Avoid medical jargon - keep it conversational

EXAMPLES:
"🩺 Did you know this simple trick can reduce back pain in 30 seconds? Your spine will thank you!"
"💊 The truth about supplements that Big Pharma doesn't want you to know..."

Generate ONLY the caption, no explanation:
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are an expert social media caption writer for healthcare content."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.8
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"❌ Caption error: {str(e)}"

# Initialize the generator
@st.cache_resource
def get_generator():
    return YouTubeCaptionGenerator()

def check_system_dependencies():
    """Check if required system dependencies are available"""
    st.subheader("🔍 System Check")
    
    # Check yt-dlp
    try:
        result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            st.success(f"✅ yt-dlp version: {result.stdout.strip()}")
        else:
            st.error(f"❌ yt-dlp failed: {result.stderr}")
    except FileNotFoundError:
        st.error("❌ yt-dlp not found")
    except Exception as e:
        st.error(f"❌ yt-dlp check failed: {str(e)}")
    
    # Check ffmpeg
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            st.success("✅ ffmpeg available")
        else:
            st.error("❌ ffmpeg not available")
    except FileNotFoundError:
        st.error("❌ ffmpeg not found")
    except Exception as e:
        st.error(f"❌ ffmpeg check failed: {str(e)}")
    
    # Check OpenAI API
    if os.getenv('OPENAI_API_KEY'):
        st.success("✅ OpenAI API key configured")
    else:
        st.error("❌ OpenAI API key missing")

# Main app
def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🎬 Jasper Caption Generator</h1>
        <p>AI-powered captions for healthcare YouTube Shorts</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Check if OpenAI API key is set
    if not os.getenv('OPENAI_API_KEY'):
        st.error("⚠️ Please set your OPENAI_API_KEY in Streamlit Cloud secrets!")
        st.stop()
    
    # Initialize generator
    generator = get_generator()
    
    # Input section
    st.subheader("📝 Enter YouTube Shorts URLs")
    
    # Add system check button
    if st.button("🔍 Check System Dependencies", help="Debug what's available on this server"):
        check_system_dependencies()
    
    # Text area for URLs
    urls_text = st.text_area(
        "Paste YouTube Shorts URLs (one per line):",
        height=150,
        placeholder="https://www.youtube.com/shorts/abc123\nhttps://www.youtube.com/shorts/def456\n\nExample to test:\nhttps://youtube.com/shorts/zfqpjjxtqCk"
    )
    
    # Process button
    if st.button("🚀 Generate Captions", type="primary"):
        if not urls_text.strip():
            st.warning("Please enter some YouTube URLs first!")
            return
        
        # Parse URLs
        urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
        
        if not urls:
            st.warning("No valid URLs found!")
            return
        
        st.info(f"Processing {len(urls)} URL(s)...")
        
        # Process each URL
        results = []
        progress_bar = st.progress(0)
        
        for i, url in enumerate(urls):
            st.write(f"**Processing {i+1}/{len(urls)}:** {url}")
            
            with st.spinner(f"Processing URL {i+1}..."):
                start_time = time.time()
                result = generator.process_shorts_url(url)
                processing_time = time.time() - start_time
                
                result['url'] = url
                result['processing_time'] = round(processing_time, 2)
                results.append(result)
                
                if result['success']:
                    st.success(f"✅ Success in {processing_time:.1f}s")
                    st.write(f"**Caption:** {result['caption']}")
                else:
                    st.error(f"❌ Failed: {result['error']}")
            
            progress_bar.progress((i + 1) / len(urls))
        
        # Results summary
        st.subheader("🎯 Results Summary")
        
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total", len(results))
        with col2:
            st.metric("Successful", len(successful))
        with col3:
            st.metric("Failed", len(failed))
        with col4:
            st.metric("Success Rate", f"{len(successful)/len(results)*100:.1f}%")
        
        # Detailed results
        st.subheader("📋 Detailed Results")
        
        for i, result in enumerate(results, 1):
            with st.expander(f"Result {i}: {result['url']}", expanded=result['success']):
                if result['success']:
                    st.markdown(f"""
                    <div class="success-box">
                        <strong>✅ Success</strong><br>
                        <strong>Caption:</strong> {result['caption']}<br>
                        <strong>Processing Time:</strong> {result['processing_time']}s
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if result.get('transcript'):
                        st.write(f"**Transcript Preview:** {result['transcript']}")
                    
                    # Copy button
                    st.code(result['caption'], language=None)
                else:
                    st.markdown(f"""
                    <div class="error-box">
                        <strong>❌ Failed</strong><br>
                        <strong>Error:</strong> {result['error']}<br>
                        <strong>Processing Time:</strong> {result['processing_time']}s
                    </div>
                    """, unsafe_allow_html=True)
        
        # Download CSV
        if results:
            st.subheader("💾 Download Results")
            
            # Create DataFrame
            df_data = []
            for result in results:
                df_data.append({
                    'URL': result['url'],
                    'Success': result['success'],
                    'Caption': result.get('caption', ''),
                    'Transcript_Preview': result.get('transcript', ''),
                    'Error': result.get('error', ''),
                    'Processing_Time': result['processing_time']
                })
            
            df = pd.DataFrame(df_data)
            csv = df.to_csv(index=False)
            
            st.download_button(
                label="📥 Download Results as CSV",
                data=csv,
                file_name=f"jasper_captions_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

if __name__ == "__main__":
    main()