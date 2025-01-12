from flask import Flask, render_template, abort, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import random
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this to a secure secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shop.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100))
    cart_items = db.relationship('CartItem', backref='user', lazy=True)
    wishlist_items = db.relationship('WishlistItem', backref='user', lazy=True)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    dress_image = db.Column(db.String(200), nullable=False)
    size = db.Column(db.String(10))
    quantity = db.Column(db.Integer, default=1)
    added_date = db.Column(db.DateTime, default=datetime.utcnow)

class WishlistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    dress_image = db.Column(db.String(200), nullable=False)
    added_date = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_dress_details(image_name):
    """Generate dress details for a specific image"""
    dress_types = [
        "Evening Gown", "Cocktail Dress", "Summer Dress", 
        "Party Dress", "Wedding Guest Dress", "Formal Dress"
    ]
    materials = [
        "Silk", "Chiffon", "Satin", "Lace", "Cotton Blend", 
        "Velvet", "Crepe", "Tulle"
    ]
    colors = [
        "Navy Blue", "Burgundy", "Emerald Green", "Royal Blue", 
        "Black", "Rose Gold", "Champagne", "Pearl White"
    ]
    
    seed = sum(ord(c) for c in image_name)
    random.seed(seed)
    
    return {
        'name': f"{random.choice(colors)} {random.choice(dress_types)}",
        'price': round(random.uniform(89.99, 299.99), 2),
        'material': random.choice(materials),
        'description': f"Beautiful {random.choice(materials).lower()} dress perfect for special occasions. "
                      f"Features elegant design and premium quality fabric.",
        'sizes': ['XS', 'S', 'M', 'L', 'XL'],
        'available_colors': random.sample(colors, 3),
        'image': image_name
    }

def get_dress_images():
    """Get all dress images from the static/images directory"""
    image_dir = os.path.join('static', 'images')
    if not os.path.exists(image_dir):
        return []
    
    valid_extensions = {'.jpg', '.jpeg', '.png'}
    images = []
    
    for filename in os.listdir(image_dir):
        _, ext = os.path.splitext(filename)
        if ext.lower() in valid_extensions:
            images.append(filename)
    
    images.sort()
    return images

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/collection')
def collection():
    images = get_dress_images()
    dresses = [get_dress_details(img) for img in images]
    return render_template('collection.html', dresses=dresses)

@app.route('/dress/<image_name>')
def dress_details(image_name):
    if image_name not in get_dress_images():
        abort(404)
    
    dress = get_dress_details(image_name)
    all_images = get_dress_images()
    related_images = [img for img in all_images if img != image_name][:4]
    related_dresses = [get_dress_details(img) for img in related_images]
    
    return render_template('dress_details.html', dress=dress, related_dresses=related_dresses)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))
        
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            name=name
        )
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('profile'))
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/profile')
@login_required
def profile():
    cart_items = [(item, get_dress_details(item.dress_image)) 
                  for item in current_user.cart_items]
    wishlist_items = [(item, get_dress_details(item.dress_image)) 
                      for item in current_user.wishlist_items]
    return render_template('profile.html', cart_items=cart_items, wishlist_items=wishlist_items)

@app.route('/add-to-cart/<image_name>', methods=['POST'])
@login_required
def add_to_cart(image_name):
    if image_name not in get_dress_images():
        flash('Invalid dress selection', 'danger')
        return redirect(url_for('collection'))
    
    size = request.form.get('size')
    if not size:
        flash('Please select a size', 'warning')
        return redirect(url_for('dress_details', image_name=image_name))
    
    # Check if item already in cart
    existing_item = CartItem.query.filter_by(
        user_id=current_user.id,
        dress_image=image_name,
        size=size
    ).first()
    
    try:
        if existing_item:
            existing_item.quantity += 1
            flash(f'Updated quantity in cart!', 'success')
        else:
            cart_item = CartItem(
                user_id=current_user.id,
                dress_image=image_name,
                size=size
            )
            db.session.add(cart_item)
            flash('Added to cart!', 'success')
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash('Error adding to cart. Please try again.', 'danger')
        print(f"Error: {str(e)}")
    
    return redirect(url_for('dress_details', image_name=image_name))

@app.route('/add-to-wishlist/<image_name>', methods=['POST'])
@login_required
def add_to_wishlist(image_name):
    if image_name not in get_dress_images():
        flash('Invalid dress selection', 'danger')
        return redirect(url_for('collection'))
    
    try:
        # Check if item already in wishlist
        existing_item = WishlistItem.query.filter_by(
            user_id=current_user.id,
            dress_image=image_name
        ).first()
        
        if not existing_item:
            wishlist_item = WishlistItem(
                user_id=current_user.id,
                dress_image=image_name
            )
            db.session.add(wishlist_item)
            db.session.commit()
            flash('Added to wishlist!', 'success')
        else:
            flash('Already in wishlist!', 'info')
    except Exception as e:
        db.session.rollback()
        flash('Error adding to wishlist. Please try again.', 'danger')
        print(f"Error: {str(e)}")
    
    return redirect(url_for('dress_details', image_name=image_name))

@app.route('/remove-from-cart/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    item = CartItem.query.get_or_404(item_id)
    if item.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
        flash('Removed from cart!', 'success')
    return redirect(url_for('profile'))

@app.route('/remove-from-wishlist/<int:item_id>', methods=['POST'])
@login_required
def remove_from_wishlist(item_id):
    item = WishlistItem.query.get_or_404(item_id)
    if item.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
        flash('Removed from wishlist!', 'success')
    return redirect(url_for('profile'))

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True) 