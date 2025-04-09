import pygame
import random
import os
from operator import attrgetter

# Initialize pygame
pygame.init()

# Screen settings
SCREEN_WIDTH, SCREEN_HEIGHT = 1080 , 960
WORLD_WIDTH = 1080
WORLD_HEIGHT = 12400  # Made the course 4x longer
CAMERA_LAG = 0.1  # Camera smoothing factor

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Racing Game")

# Modern UI Color Palette
COLORS = {
    'background': (18, 18, 18),      # Dark background
    'primary': (66, 135, 245),       # Material Blue
    'secondary': (255, 122, 89),     # Coral
    'accent': (156, 39, 176),        # Purple
    'success': (76, 175, 80),        # Green
    'white': (255, 255, 255),
    'gray': (158, 158, 158),
    'dark_gray': (66, 66, 66)
}

# Load and prepare player images
def load_player_images():
    image_dir = os.path.join(os.path.dirname(__file__), 'Players')
    image_files = [f for f in os.listdir(image_dir) if f.endswith('.jpg')]
    
    # Randomly select up to 50 files
    if len(image_files) > 50:
        image_files = random.sample(image_files, 50)
    
    images = []
    names = []
    
    for file in image_files:
        path = os.path.join(image_dir, file)
        # Load and scale image
        img = pygame.image.load(path)
        img = pygame.transform.scale(img, (50, 50))
        
        # Create a circular mask
        mask = pygame.Surface((50, 50), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255), (25, 25), 25)
        
        # Apply the mask to the image
        img = img.convert_alpha()
        img.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        
        images.append(img)
        # Get name without extension
        names.append(os.path.splitext(file)[0])
    
    # Randomize the order of players
    combined = list(zip(images, names))
    random.shuffle(combined)
    images, names = zip(*combined)
    
    return images, names

# Font setup
font = pygame.font.Font(None, 24)

class Camera:
    def __init__(self):
        self.x = 0
        self.y = 0
        self.target_y = 0
    
    def follow(self, target_y):
        # Smooth camera movement
        self.target_y = target_y - SCREEN_HEIGHT//2
        self.y += (self.target_y - self.y) * CAMERA_LAG
        # Keep camera within world bounds
        self.y = max(0, min(self.y, WORLD_HEIGHT - SCREEN_HEIGHT))
        return self.y

class Circle:
    def __init__(self, x, y, image, name):
        self.x = x
        self.y = y
        self.radius = 28
        self.image = image
        self.name = name
        self.velocity_y = 0
        self.velocity_x = 0
        self.bounce_factor = 0.85
        self.circle_bounce_factor = 1.2  # Reduce this value for less bounce
        self.friction = 0.98
        self.finished = False
        self.finish_time = None
        self.colliding = False
        self.trail = []  # Store positions for trail effect
        self.max_trail_length = 15
        self.max_velocity = 10  # Maximum velocity threshold

    def move(self):
        if not self.finished:
            self.velocity_y += 0.5  # Gravity
            self.velocity_y *= self.friction
            self.velocity_x *= self.friction
            
            self.x += self.velocity_x
            self.y += self.velocity_y

            # Add current position to trail
            self.trail.append((self.x, self.y))
            if len(self.trail) > self.max_trail_length:
                self.trail.pop(0)

            # Screen boundaries
            if self.x - self.radius < 0:
                self.x = self.radius
                self.velocity_x *= -self.bounce_factor
            elif self.x + self.radius > WORLD_WIDTH:
                self.x = WORLD_WIDTH - self.radius
                self.velocity_x *= -self.bounce_factor

            # Limit the maximum velocity
            self.velocity_x = max(min(self.velocity_x, self.max_velocity), -self.max_velocity)
            self.velocity_y = max(min(self.velocity_y, self.max_velocity), -self.max_velocity)

    def draw(self, screen, camera_y):
        screen_y = self.y - camera_y
        
        # Only draw if on screen
        if -self.radius <= screen_y <= SCREEN_HEIGHT + self.radius:
            # Draw trail
            for i, (trail_x, trail_y) in enumerate(self.trail):
                alpha = int(255 * (i / len(self.trail)))
                trail_surface = pygame.Surface((10, 10), pygame.SRCALPHA)
                pygame.draw.circle(trail_surface, (*COLORS['primary'], alpha), (5, 5), 5)
                screen.blit(trail_surface, (trail_x - 5, trail_y - camera_y - 5))

            # Draw player
            if self.colliding:
                pygame.draw.circle(screen, COLORS['accent'], 
                                 (int(self.x), int(screen_y)), 
                                 self.radius + 5)
            
            pygame.draw.circle(screen, COLORS['primary'], 
                             (int(self.x), int(screen_y)), 
                             self.radius)
            
            screen.blit(self.image, (self.x - 25, screen_y - 25))
            
            # Draw name and stats
            text_surface = font.render(f"{self.name}", True, COLORS['white'])
            #velocity_text = font.render(f"↕{abs(int(self.velocity_y))} ↔{abs(int(self.velocity_x))}", 
            #                          True, COLORS['gray'])
            
            screen.blit(text_surface, (self.x - text_surface.get_width()//2, 
                                     screen_y + self.radius + 5))
            #screen.blit(velocity_text, (self.x - velocity_text.get_width()//2, 
            #                          screen_y + self.radius + 25))

class Obstacle:
    def __init__(self, x, y, width, height, color, obstacle_type="normal"):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.type = obstacle_type
        self.angle = 0 if obstacle_type == "rotating" else None
        self.original_pos = (x, y)
        self.movement_range = 100 if obstacle_type == "moving" else 0
        self.movement_speed = 2
        self.direction = 1  # For zigzag movement

    def update(self):
        if self.type == "rotating":
            self.angle += 2
            if self.angle >= 360:
                self.angle = 0
        elif self.type == "moving":
            movement_vector = pygame.math.Vector2()
            movement_vector.from_polar((self.movement_range, pygame.time.get_ticks() * 0.1))
            self.rect.x = self.original_pos[0] + movement_vector.x
        elif self.type == "zigzag":
            self.rect.x += self.movement_speed * self.direction
            if self.rect.left <= 0 or self.rect.right >= WORLD_WIDTH:
                self.direction *= -1
        elif self.type == "bouncing":
            self.rect.y += self.movement_speed * self.direction
            if self.rect.top <= 0 or self.rect.bottom >= WORLD_HEIGHT:
                self.direction *= -1

    def draw(self, screen, camera_y):
        screen_y = self.rect.y - camera_y
        
        # Only draw if on screen
        if -self.rect.height <= screen_y <= SCREEN_HEIGHT + self.rect.height:
            if self.type == "rotating":
                surface = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
                pygame.draw.rect(surface, self.color, (0, 0, self.rect.width, self.rect.height))
                rotated_surface = pygame.transform.rotate(surface, self.angle)
                screen.blit(rotated_surface, 
                          (self.rect.centerx - rotated_surface.get_width()//2,
                           screen_y - rotated_surface.get_height()//2))
            else:
                pygame.draw.rect(screen, self.color, 
                               pygame.Rect(self.rect.x, screen_y, 
                                         self.rect.width, self.rect.height))

def check_collision(circle, obstacle):
    if obstacle.type == "rotating":
        distance = pygame.math.Vector2(circle.x - obstacle.rect.centerx,
                                     circle.y - obstacle.rect.centery).length()
        return distance < circle.radius + obstacle.rect.width/2
    else:
        return circle.y + circle.radius > obstacle.rect.top and \
               circle.y - circle.radius < obstacle.rect.bottom and \
               circle.x + circle.radius > obstacle.rect.left and \
               circle.x - circle.radius < obstacle.rect.right

def check_circle_collision(circle1, circle2):
    dx = circle1.x - circle2.x
    dy = circle1.y - circle2.y
    distance = (dx**2 + dy**2)**0.5
    if distance < circle1.radius + circle2.radius:
        overlap = 0.5 * (circle1.radius + circle2.radius - distance)
        epsilon = 1e-6  # Small value to prevent division by zero
        circle1.x += overlap * (dx / (distance + epsilon))
        circle1.y += overlap * (dy / (distance + epsilon))
        circle2.x -= overlap * (dx / (distance + epsilon))
        circle2.y -= overlap * (dy / (distance + epsilon))
        return True
    return False

def check_obstacle_intersection(obstacle1, obstacle2):
    return obstacle1.rect.colliderect(obstacle2.rect)

# Define the starting area
start_x = 200
start_y = 50
start_width = WORLD_WIDTH - 200
start_height = 100
circle_spacing = 100  # Increase spacing between circles

# Load player images and names
player_images, player_names = load_player_images()

# Generate circles for each player
circles = []
num_circles = len(player_images)
rows = int(num_circles**0.5) + 1
cols = (num_circles // rows) + 1

# Timer for loading circles in batches
batch_timer = 0
batch_interval = 1500  # 1 second interval between batches
current_batch = 0

def load_next_batch():
    global current_batch
    for i in range(current_batch * cols, min((current_batch + 1) * cols, num_circles)):
        row = i // cols
        col = i % cols
        x = start_x + col * circle_spacing
        y = start_y + row * circle_spacing
        circles.append(Circle(x, y, player_images[i], player_names[i]))
    current_batch += 1

# Generate obstacles throughout the longer course
obstacles = []

# Adding more complex obstacles
for _ in range(30):
    while True:
        new_obstacle = Obstacle(
            random.randint(20, WORLD_WIDTH-100),
            random.randint(200, WORLD_HEIGHT-200),
            100, 20, COLORS['primary'], "zigzag"
        )
        if not any(check_obstacle_intersection(new_obstacle, existing_obstacle) for existing_obstacle in obstacles):
            obstacles.append(new_obstacle)
            break

for _ in range(30):
    while True:
        new_obstacle = Obstacle(
            random.randint(20, WORLD_WIDTH-100),
            random.randint(200, WORLD_HEIGHT-200),
            100, 20, COLORS['gray'], "bouncing"
        )
        if not any(check_obstacle_intersection(new_obstacle, existing_obstacle) for existing_obstacle in obstacles):
            obstacles.append(new_obstacle)
            break

# Static obstacles
for _ in range(70):  # More obstacles for longer course
    while True:
        new_obstacle = Obstacle(
            random.randint(20, WORLD_WIDTH-100),
            random.randint(200, WORLD_HEIGHT-200),
            120, 20, COLORS['secondary'], "normal"
        )
        if not any(check_obstacle_intersection(new_obstacle, existing_obstacle) for existing_obstacle in obstacles):
            obstacles.append(new_obstacle)
            break

# Moving obstacles
for _ in range(70):
    while True:
        new_obstacle = Obstacle(
            random.randint(20, WORLD_WIDTH-100),
            random.randint(200, WORLD_HEIGHT-200),
            80, 20, COLORS['success'], "moving"
        )
        if not any(check_obstacle_intersection(new_obstacle, existing_obstacle) for existing_obstacle in obstacles):
            obstacles.append(new_obstacle)
            break

# Rotating obstacles
for _ in range(30):
    while True:
        new_obstacle = Obstacle(
            random.randint(20, WORLD_WIDTH-100),
            random.randint(200, WORLD_HEIGHT-200),
            100, 20, COLORS['accent'], "rotating"
        )
        if not any(check_obstacle_intersection(new_obstacle, existing_obstacle) for existing_obstacle in obstacles):
            obstacles.append(new_obstacle)
            break

# Finish line
finish_line = pygame.Rect(0, WORLD_HEIGHT - 50, WORLD_WIDTH, 10)

# Game state
game_started = False
start_time = None
running = True
game_ended = False
clock = pygame.time.Clock()
camera = Camera()


while running:
    screen.fill(COLORS['background'])
    current_time = pygame.time.get_ticks()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE and not game_started:
            game_started = True
            start_time = current_time

    if not game_started:
        text = font.render("Press SPACE to start!", True, COLORS['white'])
        screen.blit(text, (SCREEN_WIDTH//2 - text.get_width()//2, SCREEN_HEIGHT//2))
    else:
        if not game_ended:
            # Load circles in batches
            if current_batch * cols < num_circles and current_time - batch_timer > batch_interval:
                load_next_batch()
                batch_timer = current_time

            # Find the most advanced player for camera following
            if circles:
                lead_player = max(circles, key=lambda c: c.y if not c.finished else WORLD_HEIGHT)
            else:
                # Default camera position when no circles exist yet
                lead_player = Circle(SCREEN_WIDTH//2, start_y, None, "placeholder")  # Create temporary circle for camera
            camera_y = camera.follow(lead_player.y)

            # Draw finish line
            screen_finish_y = finish_line.y - camera_y
            if 0 <= screen_finish_y <= SCREEN_HEIGHT:
                pygame.draw.rect(screen, COLORS['white'], 
                               pygame.Rect(finish_line.x, screen_finish_y, 
                                         finish_line.width, finish_line.height))

            # Update and draw obstacles
            for obstacle in obstacles:
                obstacle.update()
                obstacle.draw(screen, camera_y)

            # Move and draw circles
            for circle in circles:
                if not circle.finished:
                    circle.move()
                    circle.colliding = False

                    # Collision with obstacles
                    for obstacle in obstacles:
                        if check_collision(circle, obstacle):
                            circle.colliding = True
                            circle.velocity_y = -circle.velocity_y * circle.bounce_factor
                            circle.velocity_x += random.uniform(-2, 2)

                    # Collision with other circles
                    for other_circle in circles:
                        if other_circle != circle and check_circle_collision(circle, other_circle):
                            circle.colliding = True
                            other_circle.colliding = True
                            # Calculate the new velocities after collision
                            dx = circle.x - other_circle.x
                            dy = circle.y - other_circle.y
                            distance = (dx**2 + dy**2)**0.5
                            if distance == 0:
                                distance = 1
                            nx = dx / distance
                            ny = dy / distance
                            p = 2 * (circle.velocity_x * nx + circle.velocity_y * ny - other_circle.velocity_x * nx - other_circle.velocity_y * ny) / (circle.radius + other_circle.radius)
                            circle.velocity_x -= p * circle.radius * nx * circle.circle_bounce_factor
                            circle.velocity_y -= p * circle.radius * ny * circle.circle_bounce_factor
                            other_circle.velocity_x += p * other_circle.radius * nx * other_circle.circle_bounce_factor
                            other_circle.velocity_y += p * other_circle.radius * ny * other_circle.circle_bounce_factor

                    # Finish line detection
                    if circle.y + circle.radius >= finish_line.top and not circle.finished:
                        circle.finished = True
                        circle.finish_time = (current_time - start_time) / 1000
                        game_ended = True  # Set the flag to end the game
                        end_time = current_time + 3000  # Set the end time to 3 seconds from now

                circle.draw(screen, camera_y)

            
        else:
            # Display the winner
            winner = min(circles, key=lambda c: c.finish_time if c.finished else float('inf'))
            text = font.render(f"{winner.name} wins with time {winner.finish_time:.2f}s!", True, COLORS['white'])
            screen.blit(text, (SCREEN_WIDTH//2 - text.get_width()//2, SCREEN_HEIGHT//2))
            # Display the winner's image and name
            # Scale the winner's image to be larger
            larger_image = pygame.transform.scale(winner.image, (100, 100))
            screen.blit(larger_image, (SCREEN_WIDTH//2 - larger_image.get_width()//2, SCREEN_HEIGHT//2 - 150))
            winner_text = font.render(f"{winner.name}", True, COLORS['white'])
            screen.blit(winner_text, (SCREEN_WIDTH//2 - winner_text.get_width()//2, SCREEN_HEIGHT//2 - 50))

    if game_ended and current_time >= end_time:
        running = False
    pygame.display.flip()
    clock.tick(60)

pygame.quit()