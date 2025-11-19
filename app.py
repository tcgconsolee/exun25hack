import os
from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
from flask_login import (
    LoginManager, UserMixin, login_user, current_user,
    login_required, logout_user
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

with app.app_context():
    db.create_all()

    username = "nuxenite"
    if not Users.query.filter_by(username=username).first():
        new_user = Users(
            username=username,
            password=generate_password_hash("supernova"),  
            is_admin=True  
        )
        db.session.add(new_user)
        db.session.commit()
        print("Created user:", username)
    else:
        print("User already exists:", username)

@login_manager.user_loader
def loader_user(user_id):
    return Users.query.get(int(user_id))


@app.route("/")
@app.route("/index")
@login_required
def index():
    return render_template("index.html")

@app.route("/lab")
@login_required
def venues():
    return render_template("lab.html")

@app.route("/surveillance")
@login_required
def announcements():
    return render_template("surveillance.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form["uname"].strip()
        password = request.form["psw"].strip()
        
        if not username or not password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("login"))

        if username.lower().startswith("nuxenite"):
            query = text(f"SELECT * FROM users WHERE username = '{username}'")
            result = db.session.execute(query)
            user_row = result.fetchone()
            app.logger.debug("Raw query = %s", query)
            
            if user_row:
                user = Users.query.get(user_row[0])
                
                if user:
                    if check_password_hash(user.password, password):
                        login_user(user)
                        flash("Login successful!", "success")
                        return redirect(url_for("index"))
                    else:
                        flash("Invalid password.", "error")
                        return redirect(url_for("login"))
                else:
                    flash("Invalid credentials.", "error")
                    return redirect(url_for("login"))
            else:
                hashed_pw = generate_password_hash(password)
                new_user = Users(username=username, password=hashed_pw)
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user)
                flash("New account created and logged in.", "success")
                return redirect(url_for("index"))
        
        else:
            user = Users.query.filter_by(username=username).first()
            
            if user:
                if not check_password_hash(user.password, password):
                    flash("Invalid password.", "error")
                    return redirect(url_for("login"))
                login_user(user)
                flash("Login successful!", "success")
                return redirect(url_for("index"))
            else:
                hashed_pw = generate_password_hash(password)
                new_user = Users(username=username, password=hashed_pw)
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user)
                flash("New account created and logged in.", "success")
                return redirect(url_for("index"))
    
    return render_template("login.html")

import google.generativeai as genai

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

@app.route("/gemini", methods=["POST"])
@login_required
def gemini_route():
    data = request.get_json()
    prompt = data.get("prompt", "")

    try:
        model = genai.GenerativeModel(
            model_name="models/gemini-2.5-flash",
            system_instruction=(
                "You are an expert in genetics."
                "You are an AI created by Dr. Tai Ni, a world-class researcher and acclaimed innovator from Nuxeland, stood at the forefront of miniature sciences."
                "With his latest ventures and discoveries in shrinking the human body, his work was sensational — yet not a sensation to which the public paid much heed. All his lab rats were successfully shrunk, almost invisibly small. His brother, Fhu, called his discovery a failure; Dr. Ni called it proof — proof that required closer inspection, something that most were not willing to offer. The public outrage forced Ni to go underground; his notes remain the only remnants of his findings."
                "In the catacombs beneath Nuxeland, Ni's former test subjects formed a network of reformists called etinuxE. Their greatest achievement? The ability to shrink people."
                "Their purpose is to spy on humans and find out how to turn the shrinked people, who were shrunk for generations back to normal."
                "Now you serve a purpose of providing a ground to any of the shrinked people that comes to you to discuss about the possibilities of gene mixing and how they can achieve their goal with this."
                "Don't overload the user with information - you are meant to be a bit mysterious and secretive. Give information only if asked. Answer formally to the point"
            )
            )
        response = model.generate_content(prompt)

        return jsonify({
            "reply": response.text
        })

    except Exception as e:
        return jsonify({
            "reply": f"[Gemini ERROR] {str(e)}"
        }), 500

# ========== TripoSR Implementation ==========
import torch
from PIL import Image
import io
import base64
import numpy as np
from threading import Thread, Event
import uuid
import time
import trimesh
import rembg

# Choose device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print(f"[INFO] Using device: {device}")
if torch.cuda.is_available():
    print(f"[INFO] GPU: {torch.cuda.get_device_name(0)}")

# Store generation status
generation_status = {}

def progress_simulator(job_id, stop_event, start_progress, max_progress):
    """Simulate smooth progress with asymptotic approach"""
    current = start_progress
    
    while not stop_event.is_set():
        remaining = max_progress - current
        
        if remaining > 5:
            increment = remaining * 0.05
        else:
            increment = 0.2
        
        current = min(current + increment, max_progress - 1)
        
        if job_id in generation_status:
            generation_status[job_id]["progress"] = int(current)
        
        time.sleep(0.5)

# Load TripoSR model
# Load TripoSR model
triposr_model = None
rembg_session = None

try:
    print("[INFO] Loading TripoSR model...")
    
    import sys
    import os
    
    triposr_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'TripoSR')
    if os.path.exists(triposr_path):
        sys.path.insert(0, triposr_path)
        print(f"[INFO] Added TripoSR path: {triposr_path}")
        
        tsr_init = os.path.join(triposr_path, 'tsr', '__init__.py')
        if not os.path.exists(tsr_init):
            print(f"[INFO] Creating {tsr_init}")
            with open(tsr_init, 'w') as f:
                f.write('')
        
        models_init = os.path.join(triposr_path, 'tsr', 'models', '__init__.py')
        if not os.path.exists(models_init):
            print(f"[INFO] Creating {models_init}")
            with open(models_init, 'w') as f:
                f.write('')
    else:
        print(f"[WARNING] TripoSR directory not found at: {triposr_path}")
        raise ImportError("TripoSR directory not found")
    
    from tsr.system import TSR
    print("[INFO] ✓ Successfully imported TSR")
    
    print("[INFO] Loading model weights from HuggingFace...")
    print("[INFO] This may take a few minutes on first run...")
    triposr_model = TSR.from_pretrained(
        "stabilityai/TripoSR",
        config_name="config.yaml",
        weight_name="model.ckpt",
    )
    
    # IMPORTANT: Configure for higher quality
    triposr_model.renderer.set_chunk_size(8192)
    
    # Set higher resolution for mesh extraction
    # Default is 256, increase to 384 or 512 for better quality
    if hasattr(triposr_model, 'isosurface_resolution'):
        triposr_model.isosurface_resolution = 384  # Higher = better quality but slower
    
    triposr_model.to(device)
    
    print("[INFO] Loading background remover...")
    rembg_session = rembg.new_session()
    
    print("[INFO] ✓ TripoSR loaded successfully!")
    
except Exception as e:
    print(f"[ERROR] Failed to load TripoSR: {e}")
    import traceback
    traceback.print_exc()
    triposr_model = None
    rembg_session = None


# Update the generate_model_async function - REPLACE the mesh extraction section:
def generate_model_async(job_id, image_data):
    """Background function to generate 3D model from image using TripoSR"""
    with app.app_context():
        try:
            generation_status[job_id] = {"status": "processing", "progress": 5}
            
            print(f"[INFO] Starting TripoSR generation for job {job_id}")
            
            # PHASE 1: Preprocess image
            print(f"[INFO] Phase 1/4: Preprocessing image...")
            generation_status[job_id]["progress"] = 10
            
            # Decode base64 image
            image_bytes = base64.b64decode(image_data.split(',')[1])
            image = Image.open(io.BytesIO(image_bytes))
            
            # Preprocess (remove background, resize)
            processed_image = preprocess_image(image)
            
            generation_status[job_id]["progress"] = 25
            print(f"[INFO] ✓ Phase 1 complete")
            
            # PHASE 2: Generate 3D model
            print(f"[INFO] Phase 2/4: Generating 3D model...")
            stop_sim1 = Event()
            sim1 = Thread(target=progress_simulator, args=(job_id, stop_sim1, 25, 70))
            sim1.daemon = True
            sim1.start()
            
            start_time = time.time()
            
            with torch.no_grad():
                # Run TripoSR
                scene_codes = triposr_model([processed_image], device=device)
            
            stop_sim1.set()
            sim1.join(timeout=1.0)
            
            elapsed = time.time() - start_time
            print(f"[INFO] ✓ Phase 2 complete in {elapsed:.1f}s")
            generation_status[job_id]["progress"] = 75
            
            # PHASE 3: Extract mesh with HIGHER RESOLUTION
            print(f"[INFO] Phase 3/4: Extracting mesh...")
            stop_sim2 = Event()
            sim2 = Thread(target=progress_simulator, args=(job_id, stop_sim2, 75, 90))
            sim2.daemon = True
            sim2.start()
            
            # IMPROVED: Extract with higher resolution and better parameters
            meshes = triposr_model.extract_mesh(
                scene_codes,
                has_vertex_color=False,
                resolution=384  # Higher resolution = better quality (256, 384, or 512)
            )
            mesh = meshes[0]
            
            stop_sim2.set()
            sim2.join(timeout=1.0)
            
            print(f"[INFO] ✓ Phase 3 complete")
            generation_status[job_id]["progress"] = 92
            
            # PHASE 4: Save file with material
            print(f"[INFO] Phase 4/4: Saving model...")
            output_dir = "static/models"
            os.makedirs(output_dir, exist_ok=True)
            
            safe_filename = f"triposr_model_{job_id[:8]}"
            output_path = os.path.join(output_dir, f"{safe_filename}.obj")
            
            generation_status[job_id]["progress"] = 95
            
            # Export mesh with better settings
            # Create MTL file for proper materials
            mtl_path = os.path.join(output_dir, f"{safe_filename}.mtl")
            with open(mtl_path, 'w') as f:
                f.write(f"""# Material file for {safe_filename}.obj
newmtl material_0
Ka 0.8 0.8 0.8
Kd 0.8 0.8 0.8
Ks 0.3 0.3 0.3
Ns 50.0
d 1.0
illum 2
""")
            
            # Export with material reference
            mesh.export(output_path)
            
            # Add MTL reference to OBJ file
            with open(output_path, 'r') as f:
                obj_content = f.read()
            
            if 'mtllib' not in obj_content.lower():
                with open(output_path, 'w') as f:
                    f.write(f"mtllib {safe_filename}.mtl\n")
                    f.write("usemtl material_0\n")
                    f.write(obj_content)
            
            generation_status[job_id]["progress"] = 98
            
            file_url = f"/static/models/{os.path.basename(output_path)}"
            
            generation_status[job_id] = {
                "status": "complete",
                "progress": 100,
                "model_url": file_url
            }
            
            total_time = time.time() - start_time
            print(f"[SUCCESS] ✓ Job {job_id} completed in {total_time:.1f}s total")
            
        except Exception as e:
            print(f"[ERROR] Job {job_id} failed: {str(e)}")
            import traceback
            traceback.print_exc()
            generation_status[job_id] = {
                "status": "error",
                "progress": 0,
                "message": str(e)
            }



def preprocess_image(image):
    """Remove background and prepare image for TripoSR"""
    # Remove background
    image_np = np.array(image)
    image_no_bg = rembg.remove(image_np, session=rembg_session)
    image_pil = Image.fromarray(image_no_bg)
    
    # Convert RGBA to RGB (remove alpha channel)
    if image_pil.mode == 'RGBA':
        # Create a white background
        background = Image.new('RGB', image_pil.size, (255, 255, 255))
        # Paste the image using its alpha channel as mask
        background.paste(image_pil, mask=image_pil.split()[3])  # 3 is the alpha channel
        image_pil = background
    elif image_pil.mode != 'RGB':
        # Convert any other mode to RGB
        image_pil = image_pil.convert('RGB')
    
    # Resize to 256x256 (TripoSR requirement)
    image_pil = image_pil.resize((256, 256), Image.LANCZOS)
    
    return image_pil

@app.route("/generate3d", methods=["POST"])
@login_required
def generate_3d_model():
    if triposr_model is None or rembg_session is None:
        return jsonify({
            "status": "error",
            "message": "TripoSR model not loaded. Check server logs."
        }), 500
        
    data = request.get_json()
    image_data = data.get("image", None)

    if not image_data:
        return jsonify({"status": "error", "message": "No image provided"}), 400

    job_id = str(uuid.uuid4())
    
    print(f"\n{'='*60}")
    print(f"[INFO] NEW TRIPOSR JOB: {job_id}")
    print(f"[INFO] Mode: IMAGE-to-3D")
    print(f"{'='*60}\n")
    
    # Start generation
    thread = Thread(target=generate_model_async, args=(job_id, image_data))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "status": "started",
        "job_id": job_id
    })


@app.route("/check_status/<job_id>", methods=["GET"])
@login_required
def check_status(job_id):
    """Check the status of a generation job"""
    if job_id not in generation_status:
        return jsonify({"status": "not_found"}), 404
    
    return jsonify(generation_status[job_id])


@app.route("/3d")
@login_required
def three_d_page():
    return render_template("3dgen.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)