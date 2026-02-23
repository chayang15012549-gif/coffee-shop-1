from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
import os
from werkzeug.utils import secure_filename
import qrcode
from io import BytesIO
from urllib.parse import urljoin
import socket

# สร้าง Flask Application
app = Flask(__name__)

# ตั้งค่า Secret Key สำหรับ Session
app.secret_key = 'deluxe_cafe_secret_key_2024'

# ตั้งค่า Database
# ใช้ SQLite เก็บไฟล์ shop.db ในตำแหน่งเดียวกับ app.py
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "shop.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# เริ่มต้น SQLAlchemy
db = SQLAlchemy(app)

# ==================== Models ====================
class Product(db.Model):
    """Model สำหรับตาราง Product"""
    __tablename__ = 'product'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)
    description = db.Column(db.String(500), nullable=True)
    is_favorite = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    def __repr__(self):
        return f'<Product {self.name}>'
    
    def to_dict(self):
        """แปลง Product object เป็น Dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'price': self.price,
            'image_url': self.image_url,
            'description': self.description,
            'is_favorite': self.is_favorite
        }

# ==================== Routes ====================

@app.route('/')
def index():
    """หน้าแรก - แสดงสินค้า เรียงลำดับโปรดด้านบน"""
    products = Product.query.order_by(Product.is_favorite.desc(), Product.id).all()
    return render_template('index.html', products=products)

@app.route('/cart')
def cart():
    """หน้าตะกร้าสินค้า"""
    return render_template('cart.html')

@app.route('/toggle-favorite/<int:product_id>', methods=['POST'])
def toggle_favorite(product_id):
    """Toggle favorite status ของสินค้า"""
    try:
        product = Product.query.get(product_id)
        if product:
            product.is_favorite = not product.is_favorite
            db.session.commit()
            return jsonify({'success': True, 'is_favorite': product.is_favorite})
        return jsonify({'success': False}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/products', methods=['GET'])
def get_products():
    """API เพื่อดึงข้อมูลสินค้าทั้งหมด"""
    products = Product.query.all()
    return jsonify([product.to_dict() for product in products])

@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """API เพื่อดึงข้อมูลสินค้าจากรหัส"""
    product = Product.query.get(product_id)
    if product:
        return jsonify(product.to_dict())
    return jsonify({'error': 'Product not found'}), 404

@app.route('/api/products', methods=['POST'])
def add_product():
    """API เพื่อเพิ่มสินค้าใหม่"""
    data = request.get_json()
    
    try:
        new_product = Product(
            name=data['name'],
            price=data['price'],
            image_url=data.get('image_url'),
            description=data.get('description')
        )
        db.session.add(new_product)
        db.session.commit()
        return jsonify({'message': 'Product added successfully', 'product': new_product.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """API เพื่ออัปเดตสินค้า"""
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    
    data = request.get_json()
    try:
        if 'name' in data:
            product.name = data['name']
        if 'price' in data:
            product.price = data['price']
        if 'image_url' in data:
            product.image_url = data['image_url']
        if 'description' in data:
            product.description = data['description']
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Product updated successfully', 'product': product.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """API เพื่อลบสินค้า"""
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    
    try:
        db.session.delete(product)
        db.session.commit()
        return jsonify({'message': 'Product deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ==================== Admin Routes ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """หน้า Login สำหรับแอดมิน"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # ตรวจสอบ username และ password
        if username == 'admin' and password == '1234':
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='❌ Username หรือ Password ไม่ถูกต้อง')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """ออกจากระบบ"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    """หน้า Dashboard แอดมิน"""
    # ตรวจสอบว่า Login แล้วหรือไม่
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    products = Product.query.all()
    return render_template('admin.html', products=products, username=session.get('username'))

@app.route('/add-product', methods=['GET', 'POST'])
def add_product_admin():
    """เพิ่มสินค้าใหม่ (Admin Page)"""
    # ตรวจสอบว่า Login แล้วหรือไม่
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        image_url = request.form.get('image_url')
        description = request.form.get('description')
        
        try:
            new_product = Product(
                name=name,
                price=float(price),
                image_url=image_url,
                description=description
            )
            db.session.add(new_product)
            db.session.commit()
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            return render_template('admin.html', error=f'❌ เพิ่มสินค้าไม่สำเร็จ: {str(e)}')
    
    return render_template('admin.html', products=Product.query.all())

@app.route('/delete-product/<int:product_id>', methods=['POST'])
def delete_product_admin(product_id):
    """ลบสินค้า (Admin)"""
    # ตรวจสอบว่า Login แล้วหรือไม่
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    try:
        product = Product.query.get(product_id)
        if product:
            db.session.delete(product)
            db.session.commit()
            return redirect(url_for('dashboard'))
        else:
            return "❌ ไม่พบสินค้า", 404
    except Exception as e:
        db.session.rollback()
        return f"❌ เกิดข้อผิดพลาด: {str(e)}", 400

@app.route('/admin')
def admin():
    """redirect ไป dashboard พอรู้ว่า /admin ถูกเรียก"""
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))

# ==================== QR Code Route ====================

@app.route('/qr')
def qr_page():
    """แสดงหน้า QR Code สำหรับสั่งซื้อ"""
    return render_template('qr.html')

@app.route('/order')
def order():
    """หน้าสั่งซื้อจาก QR Code"""
    return render_template('order.html')

@app.route('/api/qr-code')
def generate_qr_code():
    """สร้าง QR Code ที่ชี้ไปยังหน้าสั่งซื้อ"""
    try:
        # ได้ IP Address ของเซิร์ฟเวอร์
        host_ip = request.host.split(':')[0]
        if host_ip == 'localhost' or host_ip == '127.0.0.1':
            # ถ้ารัน localhost ให้ใช้ IP address จริงของเครื่อง
            hostname = socket.gethostname()
            host_ip = socket.gethostbyname(hostname)
        
        # สร้าง URL ที่เต็มไปด้วยโดเมนสำหรับ QR Code - ชี้ไปหน้า /order
        ordering_url = f'http://{host_ip}:5000' + url_for('order')
        
        # สร้าง QR Code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(ordering_url)
        qr.make(fit=True)
        
        # สร้างรูปภาพ
        img = qr.make_image(fill_color="black", back_color="white")
        
        # บันทึกลงใน BytesIO
        img_io = BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        return send_file(img_io, mimetype='image/png', as_attachment=False)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ==================== Database Initialization ====================

def seed_products():
    """เพิ่มข้อมูลตัวอย่างสินค้า 8 ชิ้น"""
    # ตรวจสอบว่ามีสินค้าอยู่หรือไม่
    product_count = db.session.query(db.func.count(Product.id)).scalar()
    
    if product_count == 0:
        print("\n🌱 Seeding sample products...")
        
        sample_products = [
            {
                'name': 'Arabica Premium',
                'price': 350.00,
                'image_url': 'https://images.unsplash.com/photo-1559056199-641a0ac8b3f7?w=300',
                'description': 'กาแฟอาราบิก้าคุณภาพสูงจากเอธิโอเปีย หอม นุ่ม ลิ้มรสความหวานธรรมชาติ'
            },
            {
                'name': 'Robusta Dark Roast',
                'price': 280.00,
                'image_url': 'https://images.unsplash.com/photo-1511537190424-6f4ee62583d1?w=300',
                'description': 'กาแฟโรบัสต้าคั่วเข้ม รสชาติกำลังขาด ที่สุด เหมาะสำหรับสายเข้มข้น'
            },
            {
                'name': 'Colombian Geisha',
                'price': 420.00,
                'image_url': 'https://images.unsplash.com/photo-1556742208-999c70e886c7?w=300',
                'description': 'กาแฟโคลัมเบีย หอม นุ่ม สด ที่สุดในเซ็ต ลูกค้าแนะนำ'
            },
            {
                'name': 'Espresso Blend',
                'price': 320.00,
                'image_url': 'https://images.unsplash.com/photo-1541895917989-a2eca1e2b7c9?w=300',
                'description': 'ผสมกาแฟสำหรับเอสเพรสโซ่ต้อง เนื้อสม่ำเสมอ หอมมากๆ'
            },
            {
                'name': 'Ethiopian Natural',
                'price': 380.00,
                'image_url': 'https://images.unsplash.com/photo-1557804506-669714531201?w=300',
                'description': 'กาแฟเอธิโอเปีย บอดี้กลาง ผสมผลไม้ ลูกค้าโปรดปรานมาก'
            },
            {
                'name': 'Kenyan AA',
                'price': 400.00,
                'image_url': 'https://images.unsplash.com/photo-1559525839-106d979bb24d?w=300',
                'description': 'กาแฟเคนยา เกรดพรีเมียม รสชาติสดใจ มีความเปรี้ยวลงตัว'
            },
            {
                'name': 'Vietnam Weasel',
                'price': 450.00,
                'image_url': 'https://images.unsplash.com/photo-1455857671898-eda6e21cc925?w=300',
                'description': 'กาแฟเวียดนาม รสชาติเฉพาะตัว หนา หวาน เข้มข้น สำหรับคนชอบกาแฟ'
            },
            {
                'name': 'Brazilian Santos',
                'price': 300.00,
                'image_url': 'https://images.unsplash.com/photo-1577934212624-a1f3a32b9b62?w=300',
                'description': 'กาแฟบราซิล เนื้อหนา หวาน ความสีชอคโกแลต เหมาะสำหรับเรียนรู้'
            }
        ]
        
        try:
            for product_data in sample_products:
                new_product = Product(
                    name=product_data['name'],
                    price=product_data['price'],
                    image_url=product_data['image_url'],
                    description=product_data['description']
                )
                db.session.add(new_product)
                print(f"  ✓ Added: {product_data['name']} - ฿{product_data['price']}")
            
            db.session.commit()
            print(f"\n✅ Successfully added 8 sample products!")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error seeding products: {e}")
    else:
        print(f"📊 {product_count} products already exist in database. Skipping seed.")

def init_db():
    """สร้าง Database และ Tables"""
    with app.app_context():
        # สร้างทุกตาราง
        db.create_all()
        print("✅ Database created successfully!")
        print(f"📁 Database file: {os.path.join(basedir, 'shop.db')}")
        
        # เพิ่มข้อมูลตัวอย่างถ้ายังไม่มี
        seed_products()
        
        # ตรวจสอบจำนวนสินค้าทั้งหมด
        product_count = db.session.query(db.func.count(Product.id)).scalar()
        print(f"📊 Total products in database: {product_count}")

# สร้าง Database เมื่อเริ่มต้นแอป
if __name__ == '__main__':
    init_db()
    
    # ได้ IP Address ของเครื่อง
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    print("\n" + "="*60)
    print("🚀 Starting Deluxe Cafe Flask App")
    print("="*60)
    print("📱 Local Access:  http://localhost:5000")
    print(f"📱 Mobile Access: http://{local_ip}:5000")
    print(f"🔧 Admin page:    http://{local_ip}:5000/admin")
    print(f"📊 QR Code:       http://{local_ip}:5000/qr")
    print(f"🛒 Order Page:    http://{local_ip}:5000/order")
    print(f"🔌 API Base URL:  http://{local_ip}:5000/api")
    print("="*60 + "\n")
    print("💡 Tip: Scan the QR Code with your phone to order!\n")
    
    # รัน Flask app - ผูกกับ 0.0.0.0 เพื่อให้สามารถเข้าจากโทรศัพท์ได้
    app.run(debug=True, host='0.0.0.0', port=5000)
