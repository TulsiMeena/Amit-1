
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import uuid
from pathlib import Path

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['DOWNLOAD_FOLDER'] = 'downloads'

# Create downloads folder if it doesn't exist
Path(app.config['DOWNLOAD_FOLDER']).mkdir(exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_video_info', methods=['POST'])
def get_video_info():
    try:
        url = request.json.get('url')
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'cookiefile': None,
            'nocheckcertificate': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            formats = []
            seen_formats = set()
            
            for f in info.get('formats', []):
                format_key = f"{f.get('resolution', 'audio')}_{f.get('ext')}"
                
                if format_key not in seen_formats:
                    has_video = f.get('vcodec') != 'none'
                    has_audio = f.get('acodec') != 'none'
                    
                    if has_video or has_audio:
                        formats.append({
                            'format_id': f.get('format_id'),
                            'ext': f.get('ext'),
                            'quality': f.get('format_note', 'unknown'),
                            'filesize': f.get('filesize'),
                            'vcodec': f.get('vcodec', 'none'),
                            'acodec': f.get('acodec', 'none'),
                            'resolution': f.get('resolution', 'audio only'),
                            'fps': f.get('fps'),
                            'tbr': f.get('tbr'),
                        })
                        seen_formats.add(format_key)
            
            return jsonify({
                'title': info.get('title'),
                'thumbnail': info.get('thumbnail'),
                'duration': info.get('duration'),
                'uploader': info.get('uploader'),
                'view_count': info.get('view_count'),
                'formats': formats
            })
    except Exception as e:
        print(f"Error in get_video_info: {str(e)}")
        return jsonify({'error': f'Failed to fetch video info: {str(e)}'}), 500

@app.route('/download', methods=['POST'])
def download_video():
    try:
        url = request.json.get('url')
        format_id = request.json.get('format_id', 'best')
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        # Generate unique filename
        download_id = str(uuid.uuid4())
        
        ydl_opts = {
            'format': format_id if format_id != 'best' else 'bestvideo+bestaudio/best',
            'outtmpl': os.path.join(app.config['DOWNLOAD_FOLDER'], f'{download_id}.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'merge_output_format': 'mp4',
            'nocheckcertificate': True,
            'geo_bypass': True,
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }] if format_id != 'best' and 'audio' not in format_id else [],
        }
        
        print(f"Downloading with format: {format_id}")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Check if file exists
            if not os.path.exists(filename):
                # Try with .mp4 extension
                filename = filename.rsplit('.', 1)[0] + '.mp4'
            
            if not os.path.exists(filename):
                raise Exception("Downloaded file not found")
            
            print(f"Download successful: {filename}")
            
        return jsonify({
            'success': True,
            'filename': os.path.basename(filename),
            'download_id': download_id
        })
    except Exception as e:
        print(f"Error in download: {str(e)}")
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

@app.route('/download_file/<filename>')
def download_file(filename):
    try:
        filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            # Try alternative extensions
            for ext in ['.mp4', '.webm', '.mkv', '.m4a']:
                alt_path = filepath.rsplit('.', 1)[0] + ext
                if os.path.exists(alt_path):
                    filepath = alt_path
                    break
        
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True, download_name=filename)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        print(f"Error in download_file: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
