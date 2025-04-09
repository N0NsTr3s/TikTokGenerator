import pygame
import math
import random
import time

pygame.init()
WIDTH, HEIGHT = 1080, 960
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Rotating Circles Game")
clock = pygame.time.Clock()

WHITE = (255, 255, 255)
COLORS = [(255, 0, 0),     # Red
          (0, 255, 0),     # Green
          (0, 0, 255),     # Blue
          (255, 255, 0),   # Yellow
          (255, 0, 255),   # Magenta
          (0, 255, 255),   # Cyan
          (255, 128, 0),   # Orange
          (128, 0, 255),   # Purple
          (255, 0, 128),   # Pink
          (0, 255, 128),   # Mint
          (128, 255, 0),   # Lime
          (0, 128, 255),   # Sky Blue
          (255, 128, 128), # Light Red
          (128, 255, 128), # Light Green
          (128, 128, 255)] # Light Blue
BLACK = (0, 0, 0)

ball_radius = 7
ball_x, ball_y = WIDTH // 2, HEIGHT // 2
ball_speed_x = 0
ball_speed_y = 0
gravity = 0.15
jump_strength = -7.5
bounce_strength = -2.5
bounce_multiplier = 1.1 

circles = []
num_circles = 50
min_radius, max_radius = 70, (num_circles//3)*num_circles
base_rotation_speed = 1.2
circle_thickness = 9

# Variables for slow motion effect
slow_motion = False
slow_motion_start = 0
slow_motion_duration = 0.5  # seconds
slow_motion_factor = 0.4  # 60% slower (40% of normal speed)

# Variables for explosion animation
particles = []
particle_lifetime = 60  # frames

def generate_circles():
    global circles
    circles = []
    for i in range(num_circles):
        radius = min_radius + (max_radius - min_radius) * (i / (num_circles - 1))
        angle = 180  # Initial gap position
        gap_size = 60
        color = random.choice(COLORS)
        rotation_speed = base_rotation_speed + (max_radius - radius) / 100
        circles.append({
            "radius": radius, 
            "angle": angle, 
            "gap_size": gap_size,
            "color": color, 
            "rotation_speed": rotation_speed
        })

def check_ball_bounds():
    global ball_x, ball_y, ball_speed_x, ball_speed_y
    
    # Calculate distance from center
    cx, cy = WIDTH // 2, HEIGHT // 2
    distance_from_center = math.hypot(ball_x - cx, ball_y - cy)
    
    # If ball is more than half the distance to edge, teleport back
    max_allowed_distance = min(WIDTH, HEIGHT) / 4  # Half of the smallest dimension divided by 2
    
    if distance_from_center > max_allowed_distance:
        ball_x, ball_y = cx, cy
        ball_speed_x, ball_speed_y = 0, 0


def draw_circles():
    for circle in circles:
        cx, cy = WIDTH // 2, HEIGHT // 2
        rect = (cx - circle["radius"], cy - circle["radius"],
                circle["radius"] * 2, circle["radius"] * 2)
        
        start_angle = math.radians(circle["angle"])
        end_angle = math.radians(circle["angle"] + (360 - circle["gap_size"]))  # Leave a visible gap
        pygame.draw.arc(screen, circle["color"], rect, start_angle, end_angle, circle_thickness)

def create_explosion(x, y, color):
    for _ in range(30):  # Create 30 particles
        angle = random.uniform(0, math.pi * 2)
        speed = random.uniform(2, 8)
        size = random.randint(2, 6)
        particles.append({
            "x": x,
            "y": y,
            "dx": math.cos(angle) * speed,
            "dy": math.sin(angle) * speed,
            "size": size,
            "color": color,
            "lifetime": particle_lifetime
        })

def update_particles():
    global particles
    for particle in particles:
        particle["x"] += particle["dx"]
        particle["y"] += particle["dy"]
        particle["lifetime"] -= 1
        # Make particles fade out
        alpha = int(255 * (particle["lifetime"] / particle_lifetime))
        r, g, b = particle["color"]
        particle["draw_color"] = (r, g, b, alpha)
    
    # Remove dead particles
    particles = [p for p in particles if p["lifetime"] > 0]

def draw_particles():
    for particle in particles:
        particle_surface = pygame.Surface((particle["size"] * 2, particle["size"] * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            particle_surface, 
            particle["draw_color"], 
            (particle["size"], particle["size"]), 
            particle["size"]
        )
        screen.blit(particle_surface, (int(particle["x"] - particle["size"]), int(particle["y"] - particle["size"])))

def check_collision():
    global ball_speed_y, ball_speed_x, ball_x, ball_y, circles, slow_motion, slow_motion_start
    cx, cy = WIDTH // 2, HEIGHT // 2
    closest_circle = None
    min_diff = float('inf')
    
    for circle in circles:
        dist = math.hypot(ball_x - cx, ball_y - cy)
        diff = abs(dist - circle["radius"])
        threshold = ball_radius + circle_thickness / 2
        if diff < threshold and diff < min_diff:
            min_diff = diff
            closest_circle = circle

    if closest_circle is None:
        return

    # Ball angle relative to center
    angle_to_ball = (math.degrees(math.atan2(ball_y - cy, ball_x - cx)) + 360) % 360

    # Compute gap start and end
    gap_start = (closest_circle["angle"]) % 360
    gap_end = (gap_start + closest_circle["gap_size"]) % 360

    if gap_start < gap_end:
        hit_gap = gap_start <= angle_to_ball <= gap_end
    else:
        hit_gap = angle_to_ball >= gap_start or angle_to_ball <= gap_end

    if hit_gap:
        # Create explosion animation at collision point
        create_explosion(ball_x, ball_y, closest_circle["color"])
        
        # Activate slow motion
        slow_motion = True
        slow_motion_start = time.time()
        
        circles.remove(closest_circle)
        adjust_circle_positions()
    else:
        ball_speed_y = bounce_strength * bounce_multiplier
        ball_speed_x = random.choice([-2, 2]) * bounce_multiplier

def adjust_circle_positions():
    """ Moves remaining circles closer to the center when one is destroyed. """
    global circles
    if len(circles) == 0:
        return
    
    try:
        new_max_radius = max_radius * 0.9  # Shrink the playable area gradually
        for i, circle in enumerate(circles):
            circle["radius"] = min_radius + (new_max_radius - min_radius) * (i / (len(circles) - 1))
            circle["rotation_speed"] = base_rotation_speed + (max_radius - circle["radius"]) / 100  # Recalculate speed
    except Exception as e:
        print(f"Error adjusting circle positions: {e}")
        pygame.quit()
        exit()

generate_circles()

time.sleep(3)  # Wait for 3 seconds before starting the game

running = True
while running:
    screen.fill(BLACK)

    draw_circles()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                ball_speed_y = jump_strength

    # Check if slow motion should end
    if slow_motion and time.time() - slow_motion_start > slow_motion_duration:
        slow_motion = False

    # Apply appropriate time factor
    time_factor = slow_motion_factor if slow_motion else 1.0

    ball_speed_y += gravity * time_factor
    ball_y += ball_speed_y * time_factor
    ball_x += ball_speed_x * time_factor

    for circle in circles:
        circle["angle"] = (circle["angle"] + circle["rotation_speed"] * time_factor) % 360

    check_collision()
    update_particles()  # Update particle positions
    check_ball_bounds()
    draw_circles()
    draw_particles()  # Draw the particles
    pygame.draw.circle(screen, WHITE, (int(ball_x), int(ball_y)), ball_radius)

    pygame.display.flip()
    clock.tick(60)

    # Stop the game if there are no more circles
    if not circles:
        running = False

pygame.quit()
