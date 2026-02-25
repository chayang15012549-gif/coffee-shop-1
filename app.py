from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
from werkzeug.utils import secure_filename
import socket
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

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

# ==================== OpenAI Configuration ====================
openai_client = None
if OPENAI_AVAILABLE:
    api_key = os.getenv('OPENAI_API_KEY')
    if api_key:
        openai_client = OpenAI(api_key=api_key)

def generate_product_description(product_name: str, product_price: float = None) -> str:
    """สร้างรายละเอียดสินค้าด้วย OpenAI API"""
    if not openai_client:
        return f"กาแฟพรีเมียม: {product_name}"
    
    try:
        price_info = f" ราคา {product_price} บาท" if product_price else ""
        prompt = f"""สร้างคำอธิบายสินค้ากาแฟสั้นๆ (ไม่เกิน 100 คำ) สำหรับ:
ชื่อสินค้า: {product_name}
{price_info}

ให้รายละเอียดเกี่ยวกับ:
- คุณสมบัติของกาแฟ
- ลักษณะรสชาติ
- อันดับเหมาะสำหรับคนไหน

ตอบเป็นภาษาไทยเท่านั้น"""
        
        message = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful coffee shop assistant that creates engaging product descriptions in Thai."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7
        )
        return message.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating description: {str(e)}")
        return f"กาแฟพรีเมียม: {product_name} - คุณภาพดี ลิ้มสดชื่น"

def ask_ai_question(question: str) -> str:
    """ตอบคำถามเกี่ยวกับกาแฟด้วย OpenAI API"""
    # First, handle preset (canned) questions with deterministic answers
    q = (question or '').strip()
    q_norm = q.lower()
    
    # Check Thai keywords BEFORE lowercasing (Thai doesn't have case anyway)
    # English keywords can use lowercased version
    
    # French and Espresso with both Thai and English
    if 'french' in q_norm or 'french press' in q_norm or 'แฟรนช์' in q:
        return (
            "วิธีชง French Press: ใส่กาแฟบดหยาบลงในหม้อ โรยลงและเทน้ำร้อน 90-96°C หมั่นนึ่ง 30 วินาที แล้วเทหมดเพิ่มพื้นให้ได้ 90-96°C เฟชเซ (plunger) โดยค่อยๆ กดลง 3-4 นาที ได้รสชาติเข้มข้นและเต็มบอดี้"
        )
    if 'espresso' in q_norm or 'เอสเพรส' in q or 'เอสเพรสโซ' in q:
        return (
            "วิธีชง เอสเพรสโซ: ใช้เครื่องชงเอสเพรสโซ ใส่กาแฟบดละเอียด (fine grind) ประมาณ 18-20 เมล็ดบด กดแรงพอสมควร (tamping) ขึ้นเครื่องชง ใช้น้ำที่อุณหภูมิ 92-96°C ความดัน 9 บาร์ ชงประมาณ 25-30 วินาที ได้น้ำกาแฟประมาณ 30 มล. ที่มีกลิ่นหอมและรสเข้มข้น"
        )
    
    # Preset mappings (matches by keyword)
    if any(k in q_norm for k in ['pour-over', 'pour over', 'pourover', 'pour-over?', 'pour'] ) or 'พัวร์' in q:
        return (
            "วิธีชง pour-over: อุ่นตัวกรวยและกระดาษกรองด้วยน้ำร้อนก่อน ใส่กาแฟบดขนาดกลาง-หยาบ (อัตราส่วนน้ำต่อกาแฟประมาณ 15:1) เทน้ำรอบแรกเล็กน้อยให้กาแฟบลูม 30-45 วินาที แล้วค่อยๆ เทน้ำเป็นวงกลมจนได้ปริมาณที่ต้องการ ระดับอุณหภูมิน้ำประมาณ 92-96°C จะได้รสชาติที่ชัดเจนและสมดุล"
        )
    if 'arabica' in q_norm or 'robusta' in q_norm or 'อาราบิก้า' in q or 'โรบัสต้า' in q:
        return (
            "ความแตกต่าง: Arabica ให้กลิ่นหอมซับซ้อนและรสชาติหวาน-เปรี้ยวเล็กน้อย มีกรดผลไม้ ส่วน Robusta มักให้คาเฟอีนมากกว่า รสเข้มและขม เหมาะสำหรับกาแฟที่ต้องการบอดี้หนาหรือผสมในเอสเพรสโซ่"
        )
    if 'สุขภาพ' in q or 'ผลกระทบ' in q or 'คนท้อง' in q or 'preg' in q_norm or 'pregnant' in q_norm:
        return (
            "ผลกระทบต่อสุขภาพ: การดื่มกาแฟในปริมาณปกติ (1-3 แก้ว/วัน) สำหรับผู้ใหญ่สุขภาพดีมักปลอดภัย คาเฟอีนอาจส่งผลต่อการนอนหรือหัวใจในบางคน ผู้ตั้งครรภ์ควรจำกัดปริมาณและปรึกษาแพทย์ หากมีภาวะสุขภาพควรปรึกษาแพทย์ก่อน"
        )
    if 'เก็บ' in q or 'storage' in q_norm:
        return (
            "วิธีเก็บเมล็ดกาแฟ: เก็บเมล็ดในภาชนะทึบแสงและปิดสนิท หลีกเลี่ยงความชื้นและความร้อน เก็บที่อุณหภูมิห้องและบดเมื่อจะชงใช้งานเพื่อรักษากลิ่นหอมและรสชาติ"
        )
    if 'สายพันธุ์' in q or 'variety' in q_norm or 'breed' in q_norm:
        return (
            "แนะนำสายพันธุ์กาแฟสำหรับเอสเพรสโซ: เลือกกาแฟคั่วเข้ม (dark roast) เช่น Brazilian Santos, Indonesian Sumatra หรอื Italian Roast ที่มีบอดี้หนาและรสขมหวม เหมาะสมำหรับการชงที่ต้องการ crema ที่สวยงาม"
        )
    if 'ลด' in q or 'reduce bitterness' in q_norm:
        return (
            "วิธีลดความขมของกาแฟ: ใช้น้ำอุณหภูมิไม่เกิน 96°C (ความร้อนจะทำให้ขม), ลดเวลาชง, หรือใช้กาแฟคั่วอ่อน แทน นอกจากนี้สามารถเพิ่มนม ครีม หรือน้ำตาลเพื่อลดความขมและรสชาติที่หนัก"
        )
    if 'ไม่ชอบ' in q or 'รสขม' in q or 'ไม่ชอบรสขม' in q or 'ไม่ชอบขม' in q:
        return (
            "เมนูแนะนำสำหรับคนไม่ชอบรสขม: ลองเมนูที่ใส่นมเยอะขึ้น เช่น Latte หรือ Flat White, หรือเลือกกาแฟคั่วอ่อน (light roast) ที่มีความเปรี้ยว-หวานแทนความขม และเพิ่มไซรัปรสหวานหรือคาราเมลตามชอบ"
        )

    # If OpenAI client is not configured, return the generic guidance message
    if not openai_client:
        return (
            "ขณะนี้ระบบ AI ยังไม่พร้อมใช้งาน แต่ฉันช่วยได้ด้วยคำแนะนำทั่วไป: - ถามเกี่ยวกับประเภทกาแฟ (เช่น Arabica, Robusta) - ถามเกี่ยวกับวิธีการชง (เช่น Espresso, Pour-over) - ถามเกี่ยวกับผลกระทบต่อสุขภาพ ขออภัย ฉันยังไม่สามารถเชื่อมต่อกับบริการ AI ได้ขณะนี้ แต่สามารถให้คำแนะนำทั่วไปเกี่ยวกับกาแฟได้ โปรดลองถามโดยระบุหัวข้อ เช่น 'วิธีชง', 'ประเภทกาแฟ' หรือ 'ผลกระทบต่อสุขภาพ'"
        )
    
    try:
        prompt = f"""คุณเป็นผู้เชี่ยวชาญด้านกาแฟและยังเป็นเจ้าหน้าที่ของร้านกาแฟ Deluxe Cafe 
กรุณาตอบคำถามต่อไปนี้เกี่ยวกับกาแฟ ประเภทกาแฟ วิธีการดื่ม สุขภาพ และสินค้าของเรา
ตอบอย่างเป็นมิตร สั้นกระชับ และมีประโยชน์ (ไม่เกิน 150 คำ)

คำถาม: {question}

ตอบเป็นภาษาไทยเท่านั้น"""
        
        message = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a friendly and knowledgeable coffee expert and barista at Deluxe Cafe coffee shop. You help customers with coffee knowledge, product information, and brewing advice in Thai."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.7
        )
        return message.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error answering question: {str(e)}")
        return f"ขออภัย ไม่สามารถประมวลผลคำถามได้ กรุณาลองใหม่"

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

@app.route('/api/generate-description', methods=['POST'])
def generate_description():
    """API เพื่อสร้างรายละเอียดสินค้าด้วย AI"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        product_name = data.get('name')
        product_price = data.get('price')
        
        if not product_name:
            return jsonify({'error': 'Product name is required'}), 400
        
        description = generate_product_description(product_name, product_price)
        return jsonify({'description': description, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 400

@app.route('/api/ask-ai', methods=['POST'])
def api_ask_ai():
    """API เพื่อถามคำถามเกี่ยวกับกาแฟ"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({'error': 'Question is required', 'success': False}), 400
        
        # จำกัดความยาวของคำถาม
        if len(question) > 500:
            return jsonify({'error': 'Question is too long (max 500 characters)', 'success': False}), 400
        
        answer = ask_ai_question(question)
        return jsonify({'answer': answer, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 400

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
    print(f"� API Base URL:  http://{local_ip}:5000/api")
    print("="*60 + "\n")
    
    # รัน Flask app - ผูกกับ 0.0.0.0 เพื่อให้สามารถเข้าจากโทรศัพท์ได้
    app.run(debug=True, host='0.0.0.0', port=5000)
