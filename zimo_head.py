import tkinter as tk
from PIL import Image, ImageTk, ImageSequence
import time
import random
import math
import os
import sys

# --- Conditional Import for OpenCV ---
try:
    import cv2
except ImportError:
    print("Warning: OpenCV (cv2) not found. Falling back to PIL for GIF loading.")
    cv2 = None
# ------------------------------------


# --- GLOBAL CONFIGURATION ---
# Physics Constants
SIM_GRAVITY = 0.5
SIM_FRICTION_X = 0.95
SIM_FRICTION_Y = 0.8
SIM_BOUNCE = -0.6


# UI/Window Settings
TASKBAR_HEIGHT = -32
TRANSPARENT_KEY = '#010101' # Key color for transparency
WINDOW_WIDTH, WINDOW_HEIGHT = 500, 500
SPRITE_WIDTH, SPRITE_HEIGHT = 120, 175


# File Paths (Update these paths to match your local setup)
IMAGE_ZIMO = "Zimo_head_Prototype/zimo.png"
ANIMATION_AURA = "Zimo_head_Prototype/aura.gif"


# AI/Interaction Settings
ATTACK_COOLDOWN_FRAMES = 20
ATTACK_PROJECTILE_SPEED = 20
CHASE_ACCELERATION = 1.2
MAX_VELOCITY_CHASE = 18
MAX_VELOCITY_ATTACK = 15
PARTICLE_LIFESPAN = 15
PROJECTILE_LIFESPAN = 40


class AnimatedDesktopEntity:
    """
    A class representing a desktop pet with physics, AI, and animated visuals.
    """
    def __init__(self):
        # 1. Check for required files before starting Tkinter
        if not os.path.exists("Zimo_head_Prototype") or \
           not os.path.exists(IMAGE_ZIMO) or \
           not os.path.exists(ANIMATION_AURA):
            print("Error: Required folder 'Zimo_head_Prototype' or files 'zimo.png'/'aura.gif' not found.")
            sys.exit(1)
            
        self.root = tk.Tk()
        self.configure_window()
        
        # --- FIX: Define State Variables before calling load_visual_assets ---
        self.position_x = self.screen_width // 2
        self.position_y = -200
        self.velocity_x = 0
        self.velocity_y = 0
        
        self.entity_state = "FALLING"
        self.behavior_mode = "IDLE"  # Initial state is IDLE
        self.facing_right = True
        self.scale_factor = 1.0 
        self.squash_stretch_factor = 1.0 
        
        # AI/Game State
        self.attack_timer = 0
        self.idle_jump_timer = 0
        self.idle_jump_cooldown = 0
        
        # Object Lists
        self.active_particles = []
        self.active_projectiles = []
        self.on_screen_texts = []

        # 2. Load Assets AFTER core state variables are defined
        self.load_visual_assets() 


        # Input Tracking
        self.drag_offset = (0, 0)
        self.last_mouse_pos = (0, 0)
        self.last_input_time = time.time()
        
        # Initialize Bindings and Menu
        self.setup_input_bindings()
        self.create_context_menu()


        # Start the application loop
        self.display_message("I AM ZIMO")
        self.simulation_loop()
        
        self.root.mainloop()


    def configure_window(self):
        """Sets up the initial Tkinter window properties."""
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.config(bg=TRANSPARENT_KEY)
        self.root.attributes('-transparentcolor', TRANSPARENT_KEY)
        
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        
        self.canvas = tk.Canvas(self.root, width=WINDOW_WIDTH, height=WINDOW_HEIGHT, 
                                 bg=TRANSPARENT_KEY, highlightthickness=0)
        self.canvas.pack()


    def setup_input_bindings(self):
        """Binds mouse and keyboard events to handler functions."""
        self.canvas.bind('<Button-1>', self.start_entity_drag)
        self.canvas.bind('<B1-Motion>', self.process_entity_drag)
        self.canvas.bind('<ButtonRelease-1>', self.end_entity_drag)
        self.canvas.bind('<Double-Button-1>', self.execute_super_jump)
        self.canvas.bind('<Button-3>', self.show_context_menu)
        
        # Global position/scale controls for quick adjustment
        self.root.bind('<Up>', lambda e: self.move_entity_by(dy=-10))
        self.root.bind('<Down>', lambda e: self.move_entity_by(dy=10))
        self.root.bind('<Left>', lambda e: self.move_entity_by(dx=-10))
        self.root.bind('<Right>', lambda e: self.move_entity_by(dx=10))
        self.root.bind('<Key-plus>', lambda e: self.modify_scale(0.1))
        self.root.bind('<Key-minus>', lambda e: self.modify_scale(-0.1))


    def create_context_menu(self):
        """Creates the right-click context menu for mode switching and scaling."""
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="😼 Chase Mode", command=lambda: self.set_behavior_mode("CHASE"))
        self.menu.add_command(label="⚔️ Attack Mode", command=lambda: self.set_behavior_mode("ATTACK"))
        self.menu.add_command(label="😺 Chill Mode", command=lambda: self.set_behavior_mode("IDLE"))
        self.menu.add_separator()
        self.menu.add_command(label="Scale Up (+)", command=lambda: self.modify_scale(0.1))
        self.menu.add_command(label="Scale Down (-)", command=lambda: self.modify_scale(-0.1))
        self.menu.add_separator()
        self.menu.add_command(label="Exit Application", command=self.root.destroy)


    def process_image_alpha(self, img):
        """Hard-cuts semi-transparent pixels to opaque or fully transparent."""
        datas = img.getdata()
        new_data = []
        for item in datas:
            # Alpha < 100 (out of 255) -> Fully transparent
            if item[3] < 100: 
                new_data.append((1, 1, 1, 0))  
            # Alpha >= 100 -> Keep original (opaque)
            else:
                new_data.append(item)  
        img.putdata(new_data)
        return img
    
    def load_visual_assets(self):
        """Loads the main entity image and the GIF animation frames."""
        # 1. Main Entity Image (Zimo)
        try:
            raw_img = Image.open(IMAGE_ZIMO).convert("RGBA")
            self.original_zimo_pil = self.process_image_alpha(raw_img) 
        except Exception as e:
            print(f"Error loading Zimo image: {e}. Using fallback.")
            self.original_zimo_pil = Image.new("RGBA", (SPRITE_WIDTH, SPRITE_HEIGHT), (100, 50, 200, 255))
            
        self.current_zimo_pil = self.original_zimo_pil.resize((SPRITE_WIDTH, SPRITE_HEIGHT), Image.Resampling.NEAREST)
        self.tk_zimo = ImageTk.PhotoImage(self.current_zimo_pil)


        # 2. Aura GIF Animation Sequence (Using cv2 if available for better transparency)
        self.aura_frames = []
        self.aura_delay_ms = 50 # Default delay
        
        if cv2:
            print("Loading Aura GIF with OpenCV for transparency fix...")
            try:
                cap = cv2.VideoCapture(ANIMATION_AURA)
                if not cap.isOpened(): raise Exception("OpenCV failed to open GIF.")
                
                while True:
                    ret, frame = cap.read()
                    if not ret: break
                    # Convert BGR frame to RGBA
                    frame_rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
                    # Convert black pixels (background) to transparent
                    lower_black = (0, 0, 0)
                    upper_black = (30, 30, 30)
                    mask = cv2.inRange(frame, lower_black, upper_black)
                    frame_rgba[mask > 0, 3] = 0
                    pil_img = Image.fromarray(frame_rgba)
                    resized_frame = pil_img.resize((350, 350), Image.Resampling.NEAREST) 
                    self.aura_frames.append(ImageTk.PhotoImage(resized_frame))
                cap.release()
                if not self.aura_frames: raise Exception("GIF contained no valid frames.")
                print(f"Loaded {len(self.aura_frames)} frames.")
            except Exception as e:
                print(f"OpenCV/Aura GIF loading error: {e}. Falling back to basic PIL.")
                self.aura_frames = []

        if not self.aura_frames:
            # PIL Fallback if cv2 fails or is not installed
            try:
                gif_img = Image.open(ANIMATION_AURA)
                self.aura_delay_ms = gif_img.info.get('duration', 50)
                print(f"Loading Aura GIF with PIL (Fallback) with {self.aura_delay_ms}ms delay...")
                for frame in ImageSequence.Iterator(gif_img):
                    frame = frame.convert("RGBA")
                    resized_frame = frame.copy().resize((350, 350), Image.Resampling.NEAREST)
                    self.aura_frames.append(ImageTk.PhotoImage(resized_frame))
                if not self.aura_frames: raise Exception("GIF contained no valid frames.")
            except Exception as e:
                print(f"Final Aura GIF loading error: {e}. Using empty fallback.")
                fallback = Image.new("RGBA", (1,1), (0,0,0,0))
                self.aura_frames = [ImageTk.PhotoImage(fallback)]


        # Canvas Layers
        # Always start with aura hidden (blank)
        key_rgb = tuple(int(TRANSPARENT_KEY[i:i+2], 16) for i in (1, 3, 5))
        initial_aura_image = ImageTk.PhotoImage(Image.new("RGB", (350, 350), key_rgb))
        self.aura_id = self.canvas.create_image(WINDOW_WIDTH//2, WINDOW_HEIGHT//2, image=initial_aura_image)
        self.zimo_id = self.canvas.create_image(WINDOW_WIDTH//2, WINDOW_HEIGHT//2, image=self.tk_zimo)
        
        # Animation State
        self.aura_index = 0
        self.aura_tick_frame = 0


    # --- INPUT/CONTROL HANDLERS ---
    def move_entity_by(self, dx=0, dy=0):
        """Adjusts the entity's root window position directly (for key bindings)."""
        self.position_x += dx
        self.position_y += dy
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{int(self.position_x)}+{int(self.position_y)}")


    def modify_scale(self, delta):
        """Adjusts the entity's visual scale and updates immediately."""
        self.scale_factor = max(0.5, min(2.0, self.scale_factor + delta))
        self.display_message(f"SCALE: {self.scale_factor:.1f}")
        self.update_visuals(force_resize=True)  


    def show_context_menu(self, event):
        """Displays the right-click menu."""
        self.menu.post(event.x_root, event.y_root)


    def set_behavior_mode(self, mode):
        """Sets the AI behavior mode and resets certain state variables."""
        self.behavior_mode = mode
        self.display_message(f"MODE: {mode}")
        if mode == "ATTACK":
            self.velocity_x *= 0.1 
            self.velocity_y *= 0.1
            # Show aura
            if self.aura_frames:
                self.canvas.itemconfig(self.aura_id, image=self.aura_frames[0])
        elif mode == "IDLE":
            self.idle_jump_timer = 0
            self.idle_jump_cooldown = 0
            self.entity_state = "IDLE"
            # Hide aura
            key_rgb = tuple(int(TRANSPARENT_KEY[i:i+2], 16) for i in (1, 3, 5))
            blank_frame = ImageTk.PhotoImage(Image.new("RGB", (350, 350), key_rgb))
            self.canvas.itemconfig(self.aura_id, image=blank_frame) 
            self.aura_index = 0
            self.aura_tick_frame = 0
        else:
            # Hide aura in CHASE and other modes
            key_rgb = tuple(int(TRANSPARENT_KEY[i:i+2], 16) for i in (1, 3, 5))
            blank_frame = ImageTk.PhotoImage(Image.new("RGB", (350, 350), key_rgb))
            self.canvas.itemconfig(self.aura_id, image=blank_frame)


    def start_entity_drag(self, event):
        """Initiates the drag operation."""
        # Check if the click is on the entity (roughly the center)
        cx, cy = WINDOW_WIDTH//2, WINDOW_HEIGHT//2
        dist = math.sqrt((event.x - cx)**2 + (event.y - cy)**2)
        if dist > SPRITE_WIDTH * self.scale_factor / 2:
            return # Ignore clicks outside the sprite area (approx)


        self.entity_state = "DRAGGING"
        self.velocity_x = 0
        self.velocity_y = 0
        # Calculate offset relative to the window center
        self.drag_offset = (event.x, event.y)
        self.last_mouse_pos = (self.root.winfo_pointerx(), self.root.winfo_pointery())
        self.last_input_time = time.time()
        self.squash_stretch_factor = 0.8
        self.generate_particles(20, particle_type='drag')


    def process_entity_drag(self, event):
        """Updates entity position and calculates velocity during drag."""
        if self.entity_state != "DRAGGING": return
        
        mx, my = self.root.winfo_pointerx(), self.root.winfo_pointery()
        now = time.time()
        
        # Calculate drag velocity for throw effect
        if now - self.last_input_time > 0.02:
            self.velocity_x = (mx - self.last_mouse_pos[0]) * 0.5
            self.velocity_y = (my - self.last_mouse_pos[1]) * 0.5
            self.last_mouse_pos = (mx, my)
            self.last_input_time = now


        # Update root window position
        # New Position = Current Mouse Position - Drag Offset
        self.position_x = mx - self.drag_offset[0] - (self.root.winfo_rootx() - self.position_x)
        self.position_y = my - self.drag_offset[1] - (self.root.winfo_rooty() - self.position_y)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{int(self.position_x)}+{int(self.position_y)}")


    def end_entity_drag(self, event):
        """Releases the drag, transitioning to FALLING state."""
        if self.entity_state == "DRAGGING":
            self.entity_state = "FALLING"


    def execute_super_jump(self, event):
        """Initiates a high jump action."""
        self.velocity_y = -13  # Lower jump power
        self.entity_state = "FALLING"
        self.generate_particles(50, particle_type='explosion')
        self.display_message(random.choice(["SUPER JUMP!",
    "MEOW!",
    "WHEE!",
    "HUH!",
    "BOING!",
    "YIPPEE!",
    "WOAH!",
    "POW!",
    "SPROING!",
    "EEK!",
    "HA!",
    "ZOOOM!",
    "BOP!",
    "BING!",
    "WHAM!",
    "HOP!",
    "YAY!",
    "?!",
    "…HUH?"]))
        # Fun: spin effect
        self.spin_frames = 12
        
    def display_message(self, text):
        """Creates a temporary, fading, and jittering text message above the entity."""
        font_spec = ("Verdana", 16, "bold")
        # Shadow text
        t_id_s = self.canvas.create_text(WINDOW_WIDTH//2 + 3, WINDOW_HEIGHT//2 - 120 + 3, text=text, 
                                             fill="black", font=font_spec, tags='message')
        # Main text
        t_id = self.canvas.create_text(WINDOW_WIDTH//2, WINDOW_HEIGHT//2 - 120, text=text, 
                                             fill="white", font=font_spec, tags='message')
        # Format: [main_id, shadow_id, life_frames, original_x, original_y]
        self.on_screen_texts.append([t_id, t_id_s, 100, WINDOW_WIDTH//2, WINDOW_HEIGHT//2 - 120])


    # --- CORE SIMULATION LOOP ---
    def simulation_loop(self):
        """The main game loop, called approximately every 16ms."""
        self.update_entity_physics()
        self.update_entity_ai()
        self.update_visuals()
        self.update_particle_effects()
        self.update_projectile_dynamics()
        self.update_messages()
        self.root.after(16, self.simulation_loop) # Target ~60 FPS (1000/60 = 16.6)


    # --- PHYSICS & AI UPDATES ---
    def update_entity_physics(self):
        """Applies gravity, friction, and boundary checks."""
        if self.entity_state == "DRAGGING": return
        
        # Apply Gravity (only if not a gliding attack)
        if self.behavior_mode != "ATTACK" or self.entity_state == "FALLING":
            self.velocity_y += SIM_GRAVITY
            self.velocity_y = min(self.velocity_y, 25)
        
        self.position_x += self.velocity_x
        self.position_y += self.velocity_y


        # Calculate Floor Position (Screen Height - Taskbar Height - Window Height offset)
        floor_y = self.screen_height - TASKBAR_HEIGHT - WINDOW_HEIGHT + 85
        
        # Floor Collision Detection
        if self.position_y >= floor_y:
            self.position_y = floor_y
            if abs(self.velocity_y) > 1:
                # Bounce and apply friction
                self.velocity_y *= SIM_BOUNCE
                self.velocity_x *= SIM_FRICTION_Y
                # Squash effect based on impact speed
                self.squash_stretch_factor = 1.25 - (abs(self.velocity_y) * 0.01)
                self.generate_particles(int(abs(self.velocity_y)), particle_type='impact')
            else:
                # Settle down
                self.velocity_y = 0
                self.velocity_x *= SIM_FRICTION_Y
                if abs(self.velocity_x) < 0.1:  
                    self.velocity_x = 0
                self.entity_state = "IDLE"
        else:
            self.entity_state = "FALLING" # Ensure state is falling if above floor


        # Apply slight friction if in the air (unless attacking)
        if self.entity_state == "FALLING" and self.behavior_mode != "ATTACK":
            self.velocity_x *= SIM_FRICTION_X


        # Screen Edge Bounce (Horizontal)
        x_min = -100 # Allow some off-screen travel
        x_max = self.screen_width - WINDOW_WIDTH + 100
        if self.position_x <= x_min:  
            self.position_x = x_min
            self.velocity_x *= -0.8
        if self.position_x >= x_max:  
            self.position_x = x_max
            self.velocity_x *= -0.8


        # If Zimo goes too high (lost), reset to floor
        if self.position_y < -WINDOW_HEIGHT:
            self.position_y = self.screen_height - TASKBAR_HEIGHT - WINDOW_HEIGHT + 85
            self.velocity_y = 0
            self.velocity_x = 0
            self.display_message("RESET!")

        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{int(self.position_x)}+{int(self.position_y)}")


    def update_entity_ai(self):
        """Handles the entity's behavior based on the current mode (CHASE, ATTACK, IDLE)."""
        if self.entity_state == "DRAGGING": return
        
        # Mouse cursor world coordinates
        mouse_x = self.root.winfo_pointerx()
        # Entity world coordinates (center of window)
        entity_center_x = self.position_x + WINDOW_WIDTH//2
        
        # Horizontal distance to mouse
        distance_x = mouse_x - entity_center_x


        if self.behavior_mode == "CHASE":
            # Apply force towards the cursor
            if abs(distance_x) > 20:
                accel = CHASE_ACCELERATION if distance_x > 0 else -CHASE_ACCELERATION
                self.velocity_x += accel
                self.velocity_x = max(-MAX_VELOCITY_CHASE, min(MAX_VELOCITY_CHASE, self.velocity_x))
                # Facing direction is set here (fix: flip in chase mode too)
                self.facing_right = distance_x > 0
                # Trigger particle effect proportional to speed
                if abs(self.velocity_x) > 3:
                    self.generate_particles(1, particle_type='trail')


        elif self.behavior_mode == "ATTACK":
            # Gliding Chase behavior
            self.entity_state = "IDLE" # Force IDLE to prevent constant gravity while attacking
            
            if abs(distance_x) > 10:
                accel = 0.9 if distance_x > 0 else -0.9
                self.velocity_x += accel
                self.velocity_x = max(-MAX_VELOCITY_ATTACK, min(MAX_VELOCITY_ATTACK, self.velocity_x))
                self.facing_right = distance_x > 0
            
            # Shooting Logic
            self.attack_timer -= 1
            if self.attack_timer <= 0:
                self.initiate_projectile(mouse_x, self.root.winfo_pointery())
                self.attack_timer = ATTACK_COOLDOWN_FRAMES # Reset cooldown
                self.squash_stretch_factor = 1.1 # Recoil effect


        elif self.behavior_mode == "IDLE" and self.entity_state == "IDLE":
            # Gentle vertical float
            self.position_y += math.sin(time.time() * 3) * 0.5 
            
            # Random jump behavior
            self.idle_jump_cooldown -= 1
            if self.idle_jump_cooldown <= 0:
                self.velocity_x = random.uniform(-4, 4)
                self.velocity_y = random.uniform(-7, -4) # Lower jump power
                self.entity_state = "FALLING"
                self.idle_jump_cooldown = random.randint(60, 240) # Jump every 1-4 seconds


    # --- VISUALS & ANIMATIONS ---
    def update_visuals(self, force_resize=False):
        """
        Handles the animation, scaling, and orientation of the entity.
        """
        
        # Aura GIF Animation (only in ATTACK mode)
        if self.behavior_mode == "ATTACK":
            self.aura_tick_frame += 1
            # Use the actual GIF frame delay to control animation speed
            if self.aura_tick_frame * 16 >= self.aura_delay_ms: 
                self.aura_tick_frame = 0
                self.aura_index = (self.aura_index + 1) % len(self.aura_frames)
                # Only update image item if frames exist
                if self.aura_frames:
                    self.canvas.itemconfig(self.aura_id, image=self.aura_frames[self.aura_index])
        
        # Squash, Stretch & Scale
        # Dampen the effect back towards 1.0
        self.squash_stretch_factor += (1.0 - self.squash_stretch_factor) * 0.15
        
        # Calculate new dimensions based on scale and squash/stretch
        new_width = int(SPRITE_WIDTH * (2 - self.squash_stretch_factor) * self.scale_factor)
        new_height = int(SPRITE_HEIGHT * self.squash_stretch_factor * self.scale_factor)
        
        # Only resize if a significant change or forced
        if new_width > 10 and new_height > 10 and (abs(self.squash_stretch_factor-1.0) > 0.01 or force_resize):
            img = self.original_zimo_pil.resize((new_width, new_height), Image.Resampling.NEAREST)
            
            # Flip logic: flip if facing left (so right is default)
            if not self.facing_right:
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            
            # Spin effect
            if hasattr(self, 'spin_frames') and self.spin_frames > 0:
                angle = (12 - self.spin_frames) * 30
                img = img.rotate(angle)
                self.spin_frames -= 1

            self.tk_zimo = ImageTk.PhotoImage(img)
            self.canvas.itemconfig(self.zimo_id, image=self.tk_zimo)


        # Subtle vertical movement for the aura/background visual
        self.canvas.coords(self.aura_id, WINDOW_WIDTH//2, WINDOW_HEIGHT//2 + math.sin(time.time()*5)*8)


    # --- PARTICLE SYSTEM ---
    def generate_particles(self, count, particle_type='impact'):
        """Generates visual particles (sparkles, explosions) based on type."""
        for _ in range(count):
            if particle_type == 'impact':
                color = random.choice(['#FFFF00', '#FF00FF', '#00FFFF'])
                size = random.randint(3, 7)
                vx = random.uniform(-4, 4)
                vy = random.uniform(-4, -1)
            elif particle_type == 'explosion':
                color = random.choice(['#FF55FF', '#AAFFFF', '#FFDD00', 'red'])
                size = random.randint(4, 10)
                vx = random.uniform(-10, 10)
                vy = random.uniform(-10, 10)
            elif particle_type == 'drag':
                color = random.choice(['#FFFFFF', '#aaffaa', '#ddaa00', 'cyan'])
                size = random.randint(4, 10)
                vx = random.uniform(-2, 2)
                vy = random.uniform(2, 5)
            elif particle_type == 'trail':
                color = random.choice(['#AA00FF', '#5500FF', '#FF00FF'])
                size = random.randint(2, 5)
                vx = random.uniform(-1, 1) * 0.5
                vy = random.uniform(-1, 1) * 0.5
            else:
                continue
            
            # Particles originate from the center of the entity window
            px = WINDOW_WIDTH//2 + random.randint(-15, 15)
            py = WINDOW_HEIGHT//2 + random.randint(-15, 15)
            
            pid = self.canvas.create_rectangle(px, py, px+size, py+size, fill=color, outline='')
            
            # Ensure particles are behind the main entity
            self.canvas.tag_lower(pid)
            self.canvas.tag_lower(self.aura_id)
            
            # Format: [id, current_x_in_window, current_y_in_window, vx, vy, life]
            self.active_particles.append([pid, px, py, vx, vy, PARTICLE_LIFESPAN])


    def update_particle_effects(self):
        """Updates the position and lifespan of all active particles."""
        for p in self.active_particles[:]:
            pid, _, _, vx, vy, life = p
            
            if self.canvas.type(pid) is None:
                self.active_particles.remove(p)
                continue
                
            self.canvas.move(pid, vx, vy)
            p[5] -= 1
            if p[5] <= 0:
                self.canvas.delete(pid)
                self.active_particles.remove(p)


    # --- PROJECTILE SYSTEM (ATTACK MODE) ---
    def initiate_projectile(self, target_x_world, target_y_world):
        """Creates a projectile aimed at the mouse cursor's world coordinates."""
        start_x_window = WINDOW_WIDTH // 2
        start_y_window = WINDOW_HEIGHT // 2
        
        # Calculate angle from entity center to world target
        angle = math.atan2(target_y_world - (self.position_y + start_y_window), 
                           target_x_world - (self.position_x + start_x_window))
        
        # Calculate velocity components
        vx = math.cos(angle) * ATTACK_PROJECTILE_SPEED
        vy = math.sin(angle) * ATTACK_PROJECTILE_SPEED
        
        pid = self.canvas.create_oval(start_x_window-5, start_y_window-5, start_x_window+5, start_y_window+5, 
                                      fill='red', outline='#FFFF00', width=3)
        # Format: [id, current_x_in_window, current_y_in_window, vx, vy, life]
        self.active_projectiles.append([pid, start_x_window, start_y_window, vx, vy, PROJECTILE_LIFESPAN])


    def create_small_explosion(self, canvas_x, canvas_y):
        """Generates a small particle explosion at a given canvas coordinate."""
        for _ in range(7): # Increased particle count
            pid = self.canvas.create_oval(canvas_x, canvas_y, canvas_x+5, canvas_y+5, fill='orange', outline='')
            # Spawn with higher velocity for a punchier explosion
            self.active_particles.append([pid, 0, 0, random.uniform(-7, 7), random.uniform(-7, 7), 10])


    def update_projectile_dynamics(self):
        """Moves projectiles and checks for collision/expiration."""
        # Get mouse position relative to entity's window for local collision check
        mouse_x_window = self.root.winfo_pointerx() - self.position_x
        mouse_y_window = self.root.winfo_pointery() - self.position_y
        
        for p in self.active_projectiles[:]:
            pid, x, y, vx, vy, life = p
            
            if self.canvas.type(pid) is None:
                self.active_projectiles.remove(p)
                continue
                
            # Visual and Data movement
            self.canvas.move(pid, vx, vy)
            p[1] += vx
            p[2] += vy
            p[5] -= 1
            
            # Collision Check: Distance squared to mouse cursor
            dx = p[1] - mouse_x_window
            dy = p[2] - mouse_y_window
            
            # Check for collision (Distance < 30) or life expiration
            if (dx*dx + dy*dy < 900) or life <= 0:  
                try:
                    # Get exact explosion coordinates before deletion
                    cx, cy = self.canvas.coords(pid)[0], self.canvas.coords(pid)[1]
                    self.create_small_explosion(cx, cy)
                except:
                    pass # Safely ignore if object was already deleted (race condition)
                
                self.canvas.delete(pid)
                self.active_projectiles.remove(p)


    # --- TEXT MESSAGE SYSTEM ---
    def update_messages(self):
        """Updates the position, jitter, and fade of on-screen text messages."""
        for t in self.on_screen_texts[:]:
            tid, tid_s, life, original_x, original_y = t
            
            # Jitter effect for an energetic look
            jit_x = random.randint(-1, 1)
            jit_y = random.randint(-1, 1)
            
            # Move text up as it fades (fading effect is simulated by movement)
            vertical_lift = (100 - life) * 1.5
            self.canvas.coords(tid, original_x + jit_x, original_y + jit_y - vertical_lift)
            self.canvas.coords(tid_s, original_x + jit_x + 2, original_y + jit_y - vertical_lift + 2)
            
            t[2] -= 1.5 # Decrease life
            if t[2] <= 0:
                self.canvas.delete(tid)
                self.canvas.delete(tid_s)
                self.on_screen_texts.remove(t)


if __name__ == "__main__":
    try:
        AnimatedDesktopEntity()
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)