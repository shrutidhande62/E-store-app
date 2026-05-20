import os
from flask import Flask, render_template, request, redirect, session, request
from models import db, Product, User, Order, CartItem, WishlistItem
import pandas as pd

from werkzeug.security import(
    generate_password_hash,
    check_password_hash
)

from flask_login import(
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

db_url = os.environ.get("DATABASE_URL", "sqlite:///database.db")

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://")

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

os.makedirs("/tmp", exist_ok=True)
db.init_app(app)

@app.context_processor
def cart_count():
    if current_user.is_authenticated:
        count = CartItem.query.filter_by(
            username = current_user.username
        ).count()
    else:
        count = 0
    
    return dict(cart_count = count)

@app.route('/')
def home():
    search = request.args.get('search')
    if search:
        products = Product.query.filter(
            Product.name.ilike(f'%{search}%')
        ).all()
    else:
        products = Product.query.all()
            
    return render_template(
        'home.html',
        products=products
        )

@app.route('/register', methods = ['GET', 'POST'])
def register():
    error = None

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            error = 'Email already registered'
            return render_template(
                'register.html',
                error = error
            )
        #create new user
        hashed_password = generate_password_hash(password)
        user = User(
            username=username,
            email=email,
            password=hashed_password
        )

        db.session.add(user)
        db.session.commit()

        return redirect('/login')
    
    return render_template(
        'register.html',
        error=error)

@app.route('/login', methods = ['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect('/')
        else:
            error = 'Invalid email or password'
        
    return render_template(
        'login.html',
        error=error
    )

@app.route('/logout')
@login_required
def logout():
    logout_user()

    return redirect('/login')

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get(product_id)
    return render_template(
        'product_detail.html',
        product=product
    )

@app.route('/add_to_cart/<int:product_id>')
@login_required
def add_to_cart(product_id):

    item = CartItem.query.filter_by(
        username = current_user.username,
        product_id = product_id
    ).first()

    if item:
        item.quantity += 1
    else:
        item = CartItem(
            username = current_user.username,
            product_id = product_id,
            quantity = 1
        )
        db.session.add(item)
    db.session.commit()
    return redirect('/')

@app.route('/add_to_wishlist/<int:product_id>')
@login_required
def add_to_wishlist(product_id):
    existing = WishlistItem.query.filter_by(
        username = current_user.username,
        product_id = product_id
    ).first()

    if not existing:
        item = WishlistItem(
            username = current_user.username,
            product_id = product_id
        )
    
        db.session.add(item)
        db.session.commit()
    return redirect('/')

@app.route('/cart')
@login_required
def cart():
    cart_items = CartItem.query.filter_by(
        username = current_user.username
    ).all()
    products = []
    total = 0
    for item in cart_items:
        product = Product.query.get(item.product_id)
        subtotal = product.price * item.quantity
        total += subtotal
        products.append({
            'id' : product.id,
            'name' : product.name,
            'price' : product.price,
            'image' : product.image,
            'quantity' : item.quantity,
            'subtotal' : subtotal
        })
        
    return render_template(
        'cart.html',
        cart_items=products,
        total = total
    )

@app.route('/wishlist')
@login_required
def wishlist():
    wishlist_items = WishlistItem.query.filter_by(
        username = current_user.username
    ).all()
    products = []
    for item in wishlist_items:
        product = Product.query.get(item.product_id)
        products.append(product)
    
    return render_template(
        'wishlist.html',
        products = products
    )

@app.route('/move_to_cart/<int:product_id>')
@login_required
def move_to_cart(product_id):
    wishlist_item = WishlistItem.query.filter_by(
        username=current_user.username,
        product_id=product_id
    ).first()
    if wishlist_item:
        cart_item = CartItem.query.filter_by(
            username=current_user.username,
            product_id=product_id
        ).first()
        if cart_item:
            cart_item.quantity += 1
        else:
            cart_item = CartItem(
                username=current_user.username,
                product_id=product_id,
                quantity=1
            )

            db.session.add(cart_item)

        db.session.delete(wishlist_item)
        db.session.commit()

    return redirect('/wishlist')

@app.route('/move_to_wishlist/<int:product_id>')
@login_required
def move_to_wishlist(product_id):

    cart_item = CartItem.query.filter_by(
        username=current_user.username,
        product_id=product_id
    ).first()
    if cart_item:
        existing = WishlistItem.query.filter_by(
            username=current_user.username,
            product_id=product_id
        ).first()
        if not existing:
            wishlist_item = WishlistItem(
                username=current_user.username,
                product_id=product_id
            )

            db.session.add(wishlist_item)

        db.session.delete(cart_item)
        db.session.commit()

    return redirect('/cart')

@app.route('/remove_from_wishlist/<int:product_id>')
@login_required
def remove_from_wishlist(product_id):
    item = WishlistItem.query.filter_by(
        username=current_user.username,
        product_id=product_id
    ).first()
    if item:
        db.session.delete(item)
        db.session.commit()

    return redirect('/wishlist')

@app.route('/increase_quantity/<int:product_id>')
@login_required
def increase_quantity(product_id):
    item = CartItem.query.filter_by(
        username = current_user.username,
        product_id = product_id
    ).first()
    if item:
        item.quantity += 1
        db.session.commit()
    return redirect(request.referrer or '/')

@app.route('/decrease_quantity/<int:product_id>')
@login_required
def decrease_quantity(product_id):
    item = CartItem.query.filter_by(
        username = current_user.username,
        product_id = product_id
    ).first()
    if item:
        item.quantity -= 1
        if item.quantity <= 0:
            db.session.delete(item)
        db.session.commit()
    return redirect(request.referrer or '/')

@app.route('/remove_from_cart/<int:product_id>')
@login_required
def remove_from_cart(product_id):
    item = CartItem.query.filter_by(
        username = current_user.username,
        product_id = product_id
    ).first()
    if item:
        db.session.delete(item)
        db.session.commit()
    return redirect(request.referrer or '/')

@app.route('/checkout')
@login_required
def checkout():
    cart_items = CartItem.query.filter_by(
        username=current_user.username
    ).all()

    if len(cart_items) == 0:
        return redirect('/cart')

    product_names = []
    total = 0

    for item in cart_items:

        product = Product.query.get(item.product_id)

        product_names.append(product.name)

        total += product.price * item.quantity

    order = Order(
        username=current_user.username,
        products=', '.join(product_names),
        total_price=total
    )

    db.session.add(order)

    # REMOVE ITEMS FROM CART
    for item in cart_items:
        db.session.delete(item)

    db.session.commit()

    return render_template(
        'success.html',
        total=total
    )

@app.route('/orders')
@login_required
def orders():
    user_orders = Order.query.filter_by(
        username = current_user.username
    ).all()

    return render_template(
        'orders.html',
        orders = user_orders
    )

@app.route('/clear')
def clear():
    session.clear()
    return 'Session Cleared'

@app.after_request
def add_header(response):

    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0"
    )

    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if Product.query.count() == 0:
            import os
            path = os.path.join(os.path.dirname(__file__), 'products.csv')
            data = pd.read_csv(path)

            for index, row in data.iterrows():
                product = Product(
                    name = row['name'],
                    price = row['price'],
                    image = row['image']
                )
                db.session.add(product)
            db.session.commit()

    app.run(debug=True)



