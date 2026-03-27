import re
import csv
import pandas as pd
from io import BytesIO, StringIO
from fpdf import FPDF
from flask import Flask, render_template, request, flash, redirect, url_for, Response, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from model import db, User, Customer, Employee, Lead, UserRole, LeadStatus, CustomerStatus, LeadSource, ActivityType
from config import Config
from flask_login import logout_user, login_required, LoginManager, UserMixin, login_user, current_user
from flask_migrate import Migrate

app = Flask(__name__, template_folder='Templates')
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
app.config.from_object(Config)
ming = Migrate(app, db)

db.init_app(app)
app.secret_key = 'glassentials_secure_secret_key'

@app.route('/')
def home():
    return render_template('Home/index.html')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Suggestion 2: Error Handling ---
@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/500.html'), 500

@app.route('/about')
def about():
    return render_template('Home/about.html')

@app.route('/home')
@login_required
def home_page():
    all_customers = Customer.query.filter_by(is_deleted=False).order_by(Customer.created_at.desc()).all()
    recent_leads = Lead.query.filter_by(is_deleted=False).order_by(Lead.created_at.desc()).limit(5).all()
    total_leads = Lead.query.filter_by(is_deleted=False).count()
    return render_template('Home/home.html', all_customers=all_customers, recent_leads=recent_leads, total_leads=total_leads)

@app.route('/view-customer/<int:customer_id>')
@login_required
def view_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    return render_template('customer/customer_profile.html', customer=customer)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        #check if user exists
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!','loginsuccess')
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('home_page'))
        else:
            flash('Invalid email or password.','loginerror')
            return redirect('/login')
    return render_template('login/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        phone_number = request.form.get('phone_number')
        role = request.form.get('role')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # 1. Empty Field Check
        if not all([username, email, phone_number, role, password, confirm_password]):
            flash('All fields are required.', 'registererror')
            return redirect(url_for('register'))

        # 2. Password Match Check
        if password != confirm_password:
            flash('Passwords do not match.', 'registererror')
            return redirect(url_for('register'))

        # 3. Email Validation
        email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(email_pattern, email):
            flash('Invalid email format.', 'registererror')
            return redirect(url_for('register'))

        # 4. Phone Validation
        if not phone_number.isdigit() or len(phone_number) != 10:
            flash('Invalid phone number. Enter 10 digits.', 'registererror')
            return redirect(url_for('register'))
        
        # 5. Password Strength Check
        if len(password) < 8 or len(password) > 12:
            flash('Password must be 8-12 characters long.', 'registererror')
            return redirect(url_for('register'))

        if not re.search(r'[A-Z]', password):
            flash('Password must contain at least 1 uppercase letter.', 'registererror')
            return redirect(url_for('register'))

        if not re.search(r'[0-9]', password):
            flash('Password must contain at least 1 number.', 'registererror')
            return redirect(url_for('register'))

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            flash('Password must contain at least 1 special character.', 'registererror')
            return redirect(url_for('register'))

        # 6. Duplicate Check (Optimized)
        existing_user = User.query.filter(
            (User.username == username) |
            (User.email == email) |
            (User.phone_number == phone_number)
        ).first()

        if existing_user:
            flash('User already exists with same username/email/phone.', 'registererror')
            return redirect(url_for('register'))

        # 7. Hash Password
        hashed_password = generate_password_hash(password)

        # 8. Create User
        new_user = User(
            username=username,
            email=email,
            phone_number=phone_number,
            role=UserRole.__members__.get(role.upper(), UserRole.EMPLOYEE) if role else UserRole.EMPLOYEE,
            password=hashed_password
        )
        db.session.add(new_user)
        db.session.flush() # Ensure new_user.id is available

        # 9. Create Employee record for the user
        new_employee = Employee(
            user_id=new_user.id,
            name=username,
            position=role
        )
        db.session.add(new_employee)
        db.session.commit()
        flash('Registration successful! Please log in.', 'registersuccess')
        return redirect(url_for('login'))

    return render_template('login/register.html')
@app.route('/customers')
@login_required
def customers():
    all_customers = Customer.query.filter_by(is_deleted=False).order_by(Customer.created_at.desc()).all()
    all_employees = Employee.query.filter_by(is_deleted=False).all()
    # Get unique cities for filter dropdown
    unique_cities = sorted(list(set(c.city for c in all_customers if c.city)))
    return render_template('customer/customer.html', customers=all_customers, employees=all_employees, cities=unique_cities)

@app.route('/export-customers/<string:format>')
@login_required
def export_customer(format):
    customers = Customer.query.filter_by(is_deleted=False).order_by(Customer.created_at.desc()).all()
    
    data = []
    for c in customers:
        data.append({
            'id': str(c.id),
            'name': str(c.name or ''),
            'email': str(c.email or ''),
            'phone': str(c.phone_number or ''),
            'address': str(c.address or '—'),
            'city': str(c.city or '—'),
            'company': str(c.company or '—'),
            'source': str(c.source.value if c.source else '—'),
            'status': str(c.status.value if c.status else 'New'),
            'created_date': c.created_at.strftime('%Y-%m-%d') if c.created_at else '—',
            'updated_date': c.updated_at.strftime('%Y-%m-%d') if c.updated_at else '—',
            'assigned_to': c.assignee.user.username if c.assignee and c.assignee.user else 'Unassigned',
            'created_by': c.creator.user.username if c.creator and c.creator.user else 'Unknown',
            'updated_by': c.updater.user.username if c.updater and c.updater.user else 'Unknown'
        })
    
    headers = ['ID', 'Name', 'Email', 'Phone','Address' ,'City', 'Company', 'Source','Status', 'Created_Date', 'Updated_Date','Assigned_To', 'Created_By', 'Updated_By']
    
    if format == 'csv':
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(headers)
        for row in data:
            cw.writerow([row[h.lower()] for h in headers])
        return Response(
            si.getvalue(),
            mimetype='text/csv',
            headers={"Content-Disposition": "attachment;filename=customers.csv"}
        )
    
    elif format == 'excel':
        df = pd.DataFrame(data)
        output = BytesIO()

        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Customers')
            workbook = writer.book
            worksheet = writer.sheets['Customers']

            gold_color = '#D4AF37'
            navy_color = '#0D1B2A'
            
            header_fmt = workbook.add_format({
                'bold': True,
                'bg_color': gold_color,
                'font_color': '#FFFFFF',
                'border': 1,
                'align': 'center',
                'valign': 'middle'
            })
            
            cell_fmt = workbook.add_format({
                'border': 1,
                'valign': 'middle',
                'font_name': 'Arial',
                'font_size': 10
            })
            
            alt_row_fmt = workbook.add_format({
                'border': 1,
                'bg_color': '#FBFAFA', 
                'valign': 'middle',
                'font_name': 'Arial',
                'font_size': 10
            })

            for col_num, value in enumerate(headers):
                worksheet.write(0, col_num, value, header_fmt)

            col_settings = [
                (0, 8, 'center'),   # ID
                (1, 20, 'left'),    # Name
                (2, 25, 'left'),    # Email
                (3, 15, 'center'),  # Phone
                (4, 30, 'left'),    # Address
                (5, 15, 'left'),    # City
                (6, 20, 'left'),    # Company
                (7, 12, 'center'),  # Source
                (8, 12, 'center'),  # Status
                (9, 15, 'center'),  # Created Date
                (10, 15, 'center'), # Updated Date
                (11, 15, 'left'),   # Assigned To
                (12, 12, 'left'),   # Created By
                (13, 12, 'left'),   # Updated By
            ]

            for col_idx, width, align in col_settings:
                fmt = workbook.add_format({'border': 1, 'align': align, 'valign': 'middle'})
                worksheet.set_column(col_idx, col_idx, width, fmt)

            worksheet.freeze_panes(1, 0) 
            worksheet.autofilter(0, 0, len(df), len(headers) - 1)
            
            for row_idx in range(1, len(df) + 1):
                if row_idx % 2 == 0:
                    for col_idx in range(len(headers)):
                        align = next(s[2] for s in col_settings if s[0] == col_idx)
                        row_fmt = workbook.add_format({
                            'bg_color': '#F8F9FA', 
                            'border': 1, 
                            'align': align, 
                            'valign': 'middle'
                        })
                        val = df.iloc[row_idx-1, col_idx]
                        worksheet.write(row_idx, col_idx, val, row_fmt)

        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name="customers_report.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    elif format == 'pdf':
        from datetime import datetime
        class PDF(FPDF):
            def footer(self):
                self.set_y(-15)
                self.set_font('helvetica', 'I', 8)
                self.set_text_color(128)
                self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

        pdf = PDF(orientation='L', unit='mm', format='A4')
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        pdf.set_font("helvetica", 'B', 16)
        pdf.set_text_color(13, 27, 42) # Navy
        pdf.cell(0, 15, "Customer Management Report", 0, 1, 'L')
        pdf.set_font("helvetica", size=9)
        pdf.set_text_color(100)
        current_date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        pdf.cell(0, 5, f"Date Generated: {current_date_str}", 0, 1, 'L')
        pdf.ln(10)
        widths = [8, 25, 30, 18, 35, 18, 25, 15, 15, 18, 18, 18, 18, 18]
        
        pdf.set_font("helvetica", 'B', 7)
        pdf.set_fill_color(212, 175, 55) 
        pdf.set_text_color(255)
        h = 8
        for i, header in enumerate(headers):
            pdf.cell(widths[i], h, header, border=1, fill=True, align='C')
        pdf.ln()

        pdf.set_font("helvetica", size=7)
        pdf.set_text_color(0)
        
        for idx, row in enumerate(data):
            if idx % 2 == 0:
                pdf.set_fill_color(248, 249, 250)
            else:
                pdf.set_fill_color(255, 255, 255)
            
            for i, header in enumerate(headers):
                val = str(row.get(header.lower(), ''))
                pdf.cell(widths[i], h, val[:25], border=1, fill=True, align='L')
            pdf.ln()
            
        pdf_output = pdf.output()
        buffer = BytesIO(pdf_output)
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name="customers_report.pdf",
            mimetype='application/pdf'
        )
    
    flash('Invalid format or export error.', 'customererror')
    return redirect(url_for('customers'))

@app.route('/add-customer', methods=['GET', 'POST'])
@login_required
def add_customer():
    if request.method == 'POST':
        name         = request.form.get('name', '').strip()
        email        = request.form.get('email', '').strip()
        phone_number = re.sub(r'\D', '', request.form.get('phone_number', ''))  # strip non-digits
        address      = request.form.get('address', '').strip()
        city         = request.form.get('city', '').strip()
        company      = request.form.get('company', '').strip()
        source       = request.form.get('source', '').strip()
        status       = request.form.get('status', 'New')
        notes        = request.form.get('notes', '').strip()
        assigned_to_id = request.form.get('assigned_to')
        if not assigned_to_id or assigned_to_id == 'unassigned':
            assigned_to_id = None
        else:
            assigned_to_id = int(assigned_to_id)

        # Basic validation
        if not all([name, email, phone_number]):
            flash('Name, Email, and Phone Number are required.', 'customererror')
            return redirect(url_for('add_customer'))

        if len(phone_number) != 10:
            flash('Phone number must be exactly 10 digits (digits only).', 'customererror')
            return redirect(url_for('add_customer'))

        # Check duplicate email
        if Customer.query.filter_by(email=email, is_deleted=False).first():
            flash('A customer with this email already exists.', 'customererror')
            return redirect(url_for('add_customer'))

        # Map display values ("Website") to Enum instances
        source_map = {e.value: e for e in LeadSource}
        status_map = {e.value: e for e in CustomerStatus}
        new_customer = Customer(
            name=name,
            email=email,
            phone_number=phone_number,
            address=address,
            city=city,
            company=company,
            source=source_map.get(source, LeadSource.OTHER),
            status=status_map.get(status, CustomerStatus.REQUIREMENT_UNDERSTOOD), # Changed default status
            notes=notes,
            created_by=current_user.employee.id,
            assigned_to=assigned_to_id
        )
        try:
            db.session.add(new_customer)
            db.session.commit()
            flash('Customer added successfully!', 'customersuccess')
            return redirect(url_for('customers'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving customer: {str(e)}', 'customererror')
            return redirect(url_for('add_customer'))

    employees = Employee.query.filter_by(is_deleted=False).all()
    return render_template('customer/addcustomer.html', employees=employees)
@app.route('/edit-customer/<int:customer_id>', methods=['GET', 'POST'])
@login_required
def edit_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    if request.method == 'POST':
        name         = request.form.get('name', '').strip()
        email        = request.form.get('email', '').strip()
        phone_number = re.sub(r'\D', '', request.form.get('phone_number', ''))  # strip non-digits
        address      = request.form.get('address', '').strip()
        city         = request.form.get('city', '').strip()
        company      = request.form.get('company', '').strip()
        source       = request.form.get('source', '').strip()
        status       = request.form.get('status', 'New')
        notes        = request.form.get('notes', '').strip()
        assigned_to_id = request.form.get('assigned_to')
        if not assigned_to_id or assigned_to_id == 'unassigned':
            assigned_to_id = None
        else:
            assigned_to_id = int(assigned_to_id)

        # Validation
        if not all([name, email, phone_number]):
            flash('Name, Email, and Phone Number are required.', 'customererror')
            return redirect(url_for('edit_customer', customer_id=customer_id))

        if len(phone_number) != 10:
            flash('Phone number must be exactly 10 digits.', 'customererror')
            return redirect(url_for('edit_customer', customer_id=customer_id))

        # Check for duplicate email excluding current customer
        existing = Customer.query.filter(Customer.email == email, Customer.id != customer_id, Customer.is_deleted == False).first()
        if existing:
            flash('Another customer with this email already exists.', 'customererror')
            return redirect(url_for('edit_customer', customer_id=customer_id))

        source_map = {e.value: e for e in LeadSource}
        status_map = {e.value: e for e in CustomerStatus}
        customer.name = name
        customer.email = email
        customer.phone_number = phone_number
        customer.address = address
        customer.city = city
        customer.company = company
        customer.source = source_map.get(source, LeadSource.OTHER)
        customer.status = status_map.get(status, CustomerStatus.NEW)
        customer.notes = notes
        customer.assigned_to = assigned_to_id
        customer.updated_by = current_user.employee.id

        try:
            db.session.commit()
            flash('Customer updated successfully!', 'customersuccess')
            return redirect(url_for('customers'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating customer: {str(e)}', 'customererror')
            return redirect(url_for('edit_customer', customer_id=customer_id))

    employees = Employee.query.filter_by(is_deleted=False).all()
    return render_template('customer/editcustomer.html', customer=customer, customer_id=customer_id, employees=employees)

@app.route('/delete-customer/<int:customer_id>', methods=['POST'])
@login_required
def delete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    customer.is_deleted = True
    db.session.commit()
    flash('Customer deleted successfully.', 'customersuccess')
    return redirect(url_for('customers'))
@app.route('/bulk-upload', methods=['GET', 'POST'])
@login_required
def bulk_upload():
    if request.method == 'POST':
        file = request.files.get('customer_file')
        if not file:
            flash('No file uploaded.', 'customererror')
            return redirect(url_for('bulk_upload'))
        try:
            df = pd.read_csv(file).fillna('')
            # Case-insensitive column search
            col_map = {c.lower(): c for c in df.columns}
            
            req_check = {'name', 'email', 'phone'}
            if not req_check.issubset(set(col_map.keys())):
                flash(f'Missing required columns: {", ".join(req_check)}', 'customererror')
                return redirect(url_for('bulk_upload'))
            
            success_count = 0
            errors = []
            source_map = {e.value.lower(): e for e in LeadSource}
            status_map = {e.value.lower(): e for e in CustomerStatus}
            
            for idx, row in df.iterrows():
                row_num = idx + 2
                # Helper to get column regardless of case
                def get_val(key):
                    c = col_map.get(key.lower())
                    return str(row[c]).strip() if c else ''

                name = get_val('name')
                email = get_val('email')
                phone_raw = get_val('phone')
                # Handle floats like 123.0 -> 123
                if phone_raw.endswith('.0'): phone_raw = phone_raw[:-2]
                phone_number = re.sub(r'\D', '', phone_raw)
                
                address = get_val('address')
                city = get_val('city')
                company = get_val('company')
                source_str = get_val('source').lower()
                status_str = get_val('status').lower()
                
                assigned_to_email = get_val('assigned_to')
                assigned_to_id = current_user.employee.id
                if assigned_to_email and assigned_to_email.lower() not in ['', 'nan', 'none']:
                    assigned_emp = Employee.query.join(User).filter(User.email == assigned_to_email).first()
                    if assigned_emp: assigned_to_id = assigned_emp.id

                if not all([name, email, phone_number]) or name.lower() == 'nan':
                    errors.append(f"Row {row_num}: Fields missing")
                    continue
                if len(phone_number) != 10:
                    errors.append(f"Row {row_num}: Phone not 10 digits ({phone_number})")
                    continue
                if Customer.query.filter_by(email=email, is_deleted=False).first():
                    errors.append(f"Row {row_num}: Email duplicate")
                    continue
                if Customer.query.filter_by(phone_number=phone_number, is_deleted=False).first():
                    errors.append(f"Row {row_num}: Phone duplicate")
                    continue
                    
                new_customer = Customer(
                    name=name,
                    email=email,
                    phone_number=phone_number,
                    address=address,
                    city=city,
                    company=company,
                    source=source_map.get(source_str, LeadSource.OTHER),
                    status=status_map.get(status_str, CustomerStatus.NEW),
                    created_by=current_user.employee.id,
                    assigned_to=assigned_to_id
                )
                db.session.add(new_customer)
                success_count += 1
            
            if success_count > 0:
                db.session.commit()
                if errors:
                    msg = f"Imported {success_count}. Issues: " + ", ".join(errors[:3])
                    if len(errors) > 3: msg += "..."
                    flash(msg, 'customersuccess')
                else:
                    flash(f'Successfully imported {success_count} customers!', 'customersuccess')
                return redirect(url_for('customers'))
            else:
                if errors:
                    msg = "No customers imported. Issues: " + ", ".join(errors[:3])
                    if len(errors) > 3: msg += "..."
                    flash(msg, 'customererror')
                return redirect(url_for('bulk_upload'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing file: {str(e)}', 'customererror')
            return redirect(url_for('bulk_upload'))
    return render_template('customer/bulkuploadcustomer.html')
@app.route('/download-template')
@login_required
def download_template():
    template_path = 'static/templates/bulk_upload_template.csv'
    return send_file(template_path, as_attachment=True, download_name='bulk_upload_template.csv')
@app.route('/employee')
@login_required
def employee():
    all_employees = Employee.query.filter_by(is_deleted=False).all()
    return render_template('employee/employee.html', employees=all_employees)
@app.route('/add-employee', methods=['GET', 'POST'])
@login_required
def add_employee():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone_number = request.form.get('phone_number')
        position = request.form.get('position')

        if not all([name, email, phone_number, position]):
            flash('All fields are required.', 'employeeerror')
            return redirect(url_for('add_employee'))

        if User.query.filter_by(email=email).first():
            flash('User/Employee with this email already exists.', 'employeeerror')
            return redirect(url_for('add_employee'))

        # Create linked User account with default password
        new_user = User(
            username=name.lower().replace(" ", "_"),
            email=email,
            phone_number=phone_number,
            role=UserRole.EMPLOYEE,
            password=generate_password_hash('Glass@123') # Default password
        )
        db.session.add(new_user)
        db.session.flush()

        new_employee = Employee(
            user_id=new_user.id,
            name=name,
            position=position
        )
        db.session.add(new_employee)
        db.session.commit()
        flash(f'Employee added successfully! Default password is Glass@123', 'employeesuccess')
        return redirect(url_for('employee'))

    return render_template('employee/add_employee.html')
@app.route('/edit-employee/<int:employee_id>', methods=['GET', 'POST'])
@login_required
def edit_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone_number = re.sub(r'\D', '', request.form.get('phone_number', ''))
        position = request.form.get('position', '').strip()

        if not all([name, email, phone_number, position]):
            flash('All required fields must be filled.', 'employeeerror')
            return redirect(url_for('edit_employee', employee_id=employee_id))

        if len(phone_number) != 10:
            flash('Phone number must be 10 digits.', 'employeeerror')
            return redirect(url_for('edit_employee', employee_id=employee_id))

        # Check duplicate email excluding current employee
        existing_user = User.query.filter(User.email == email, User.id != employee.user_id).first()
        if existing_user:
            flash('Another user/employee with this email already exists.', 'employeeerror')
            return redirect(url_for('edit_employee', employee_id=employee_id))

        employee.name = name
        employee.position = position
        
        # Update linked User account
        employee.user.email = email
        employee.user.phone_number = phone_number
        
        try:
            db.session.commit()
            flash('Employee profile updated successfully!', 'employeesuccess')
            return redirect(url_for('employee'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'employeeerror')
            return redirect(url_for('edit_employee', employee_id=employee_id))

    return render_template('employee/editemployee.html', employee=employee)
@app.route('/delete-employee/<int:employee_id>', methods=['POST'])
@login_required
def delete_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    employee.is_deleted=True
    db.session.commit()
    flash('Employee deleted successfully!', 'employeesuccess')
    return redirect(url_for('employee'))
@app.route('/leads')
@login_required
def leads():
    all_leads = Lead.query.filter_by(is_deleted=False).order_by(Lead.created_at.desc()).all()
    all_employees = Employee.query.filter_by(is_deleted=False).all()
    # Get unique status/sources from Enum for filters? Actually Enum is fine, we can hardcode filters in template.
    return render_template('Leads/Lead.html', leads=all_leads, employees=all_employees)

@app.route('/view-lead/<int:lead_id>')
@login_required
def view_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    return render_template('Leads/lead_profile.html', lead=lead)
@app.route('/add-lead', methods=['GET', 'POST'])
@login_required
def add_lead():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone_number = request.form.get('phone')
        company = request.form.get('company')
        source = request.form.get('source')
        status = request.form.get('status')
        address = request.form.get('address')
        city = request.form.get('city')
        notes = request.form.get('notes', '').strip()
        assigned_to_id = request.form.get('assigned_to')
        if not assigned_to_id or assigned_to_id == 'unassigned':
            assigned_to_id = None
        else:
            assigned_to_id = int(assigned_to_id)

        if not all([name, email, phone_number]):
            flash('Name, Email, and Phone Number are required.', 'leadserror')
            return redirect(url_for('add_lead'))

        if len(phone_number) != 10:
            flash('Phone number must be exactly 10 digits.', 'leadserror')
            return redirect(url_for('add_lead'))

        if Lead.query.filter_by(email=email, is_deleted=False).first():
            flash('A lead with this email already exists.', 'leadserror')
            return redirect(url_for('add_lead'))

        source_map = {e.value: e for e in LeadSource}
        status_map = {e.value: e for e in LeadStatus}
        new_lead = Lead(
            name=name,
            email=email,
            phone_number=phone_number,
            company=company,
            source=source_map.get(source, LeadSource.OTHER),
            status=status_map.get(status, LeadStatus.NEW),
            notes=notes,
            address=address,
            city=city,
            created_by=current_user.employee.id,
            assigned_to=assigned_to_id
        )
        try:
            db.session.add(new_lead)
            db.session.commit()
            flash('Lead added successfully!', 'leadssuccess')
            return redirect(url_for('leads'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving lead: {str(e)}', 'leadserror')
            return redirect(url_for('add_lead'))

    employees = Employee.query.filter_by(is_deleted=False).all()
    return render_template('Leads/addLead.html', employees=employees)
@app.route('/edit-lead/<int:lead_id>', methods=['GET', 'POST'])
@login_required
def edit_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone_number = re.sub(r'\D', '', request.form.get('phone', ''))
        company = request.form.get('company', '').strip()
        source = request.form.get('source', '').strip()
        status = request.form.get('status', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        notes = request.form.get('notes', '').strip()
        assigned_to_id = request.form.get('assigned_to')
        if not assigned_to_id or assigned_to_id == 'unassigned':
            assigned_to_id = None
        else:
            assigned_to_id = int(assigned_to_id)

        if not all([name, email, phone_number]):
            flash('Name, Email, and Phone Number are required.', 'leadserror')
            return redirect(url_for('edit_lead', lead_id=lead_id))

        if len(phone_number) != 10:
            flash('Phone number must be exactly 10 digits.', 'leadserror')
            return redirect(url_for('edit_lead', lead_id=lead_id))

        existing = Lead.query.filter(Lead.email == email, Lead.id != lead_id, Lead.is_deleted == False).first()
        if existing:
            flash('Another lead with this email already exists.', 'leadserror')
            return redirect(url_for('edit_lead', lead_id=lead_id))

        source_map = {e.value: e for e in LeadSource}
        status_map = {e.value: e for e in LeadStatus}
        lead.name = name
        lead.email = email
        lead.phone_number = phone_number
        lead.company = company
        lead.source = source_map.get(source, LeadSource.OTHER)
        lead.status = status_map.get(status, LeadStatus.NEW)
        lead.address = address
        lead.city = city
        lead.notes = notes
        lead.assigned_to = assigned_to_id
        lead.updated_by = current_user.employee.id

        try:
            db.session.commit()
            flash('Lead updated successfully!', 'leadssuccess')
            return redirect(url_for('leads'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating lead: {str(e)}', 'leadserror')
            return redirect(url_for('edit_lead', lead_id=lead_id))
    employees = Employee.query.filter_by(is_deleted=False).all()
    return render_template('Leads/editLead.html', lead=lead, lead_id=lead_id, employees=employees)
@app.route('/delete-lead/<int:lead_id>', methods=['POST'])
@login_required
def delete_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    lead.is_deleted = True
    db.session.commit()
    flash('Lead deleted successfully!', 'leadssuccess')
    return redirect(url_for('leads'))
@app.route('/export-leads/<string:format>')
@login_required
def export_leads(format):
    leads = Lead.query.filter_by(is_deleted=False).order_by(Lead.created_at.desc()).all()
    
    data = []
    for l in leads:
        data.append({
            'id': str(l.id),
            'name': str(l.name or ''),
            'email': str(l.email or ''),
            'phone': str(l.phone_number or ''),
            'company': str(l.company or '—'),
            'source': str(l.source.value if l.source else '—'),
            'status': str(l.status.value if l.status else 'New'),
            'created_date': l.created_at.strftime('%Y-%m-%d') if l.created_at else '—',
            'updated_date': l.updated_at.strftime('%Y-%m-%d') if l.updated_at else '—',
            'assigned_to': l.assignee.user.username if l.assignee and l.assignee.user else 'Unassigned',
            'created_by': l.creator.user.username if l.creator and l.creator.user else 'Unknown',
            'updated_by': l.updater.user.username if l.updater and l.updater.user else 'Unknown'
        })
    
    headers = ['ID', 'Name', 'Email', 'Phone', 'Company', 'Source','Status', 'Created_Date', 'Updated_Date','Assigned_To', 'Created_By', 'Updated_By']
    
    if format == 'csv':
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(headers)
        for row in data:
            cw.writerow([row[h.lower()] for h in headers])
        return Response(
            si.getvalue(),
            mimetype='text/csv',
            headers={"Content-Disposition": "attachment;filename=leads.csv"}
        )
    
    # Excel and PDF export logic would be similar to customers, adjusted for lead fields
    elif format=='excel':
        df=pd.DataFrame(data)
        output=BytesIO()
        
        with pd.ExcelWriter(output,engine='xlsxwriter') as writer:
            df.to_excel(writer,index=False,sheet_name='Leads')
            workbook=writer.book
            worksheet=writer.sheets['Leads']
            
            gold_color='#D4AF37'
            navy_color='#0D1B2A'
            
            header_fmt=workbook.add_format({
                'bold':True,
                'bg_color':gold_color,
                'font_color':'#FFFFFF',
                'border':1,
                'align':'center',
                'valign':'middle'
            })
            
            cell_fmt=workbook.add_format({
                'border':1,
                'valign':'middle',
                'font_name':'Arial',
                'font_size':10
            })
            
            alt_row_fmt=workbook.add_format({
                'border':1,
                'bg_color':'#FBFAFA',
                'valign':'middle',
                'font_name':'Arial',
                'font_size':10
            })
            
            for col_num, value in enumerate(headers):
                worksheet.write(0,col_num,value,header_fmt)
                
            col_settings=[
                (0, 8, 'center'),
                (1, 20, 'left'),
                (2, 25, 'left'),
                (3, 15, 'center'),
                (4, 30, 'left'),
                (5, 15, 'left'),
                (6, 20, 'left'),
                (7, 12, 'center'),
                (8, 12, 'center'),
                (9, 15, 'center'),
                (10, 15, 'center'),
                (11, 15, 'left'),
                (12, 12, 'left'),
                (13, 12, 'left'),   
            ]
            
            for col_idx, width, align in col_settings:
                fmt=workbook.add_format({'border':1, 'align':align, 'valign':'middle'})
                worksheet.set_column(col_idx, col_idx, width, fmt)
            
            worksheet.freeze_panes(1,0)
            worksheet.autofilter(0, 0, len(df), len(headers)-1)
            
            for row_idx in range(1, len(df)+1):
                if row_idx % 2==0:
                    for col_idx in range(len(headers)):
                        align=next(s[2] for s in col_settings if s[0]== col_idx)
                        row_fmt=workbook.add_format({
                            'bg_color':'#F8F9FA',
                            'border':1,
                            'align':align,
                            'valign':'middle'
                        })
                        val = df.iloc[row_idx-1, col_idx]
                        worksheet.write(row_idx, col_idx, val, row_fmt)
        
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name="Leads_report.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    elif format=='pdf':
        from datetime import datetime
        class PDF(FPDF):
            def footer(self):
                self.set_y(-15)
                self.set_font('helvetica','I',8)
                self.cell(0,10, f'Page {self.page_no()}', 0, 0, 'C')
        pdf=PDF(orientation='L',unit='mm', format='A4')
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        pdf.set_font("helvetica", 'B', 16)
        pdf.set_text_color(13,27,42)
        pdf.cell(0, 15, "Lead Management Report", 0, 1, 'L')
        pdf.set_font("helvetica",size=9)
        pdf.set_text_color(100)
        current_date_str=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        pdf.cell(0, 5, f"Data Generated: {current_date_str}", 0, 1, 'L')
        pdf.ln(10)
        widths=[10, 20, 30, 22, 25, 20, 25, 20, 20, 25, 20, 20]
        
        pdf.set_font("helvetica", 'B', 7)
        pdf.set_fill_color(212, 175, 55)
        pdf.set_text_color(255)
        h=8
        for i, header_val in enumerate(headers):
            pdf.cell(widths[i], h, header_val, border=1, fill=True, align='C')
        pdf.ln()
        
        pdf.set_font("helvetica", size=7)
        pdf.set_text_color(0)
        
        for idx, row in enumerate(data):
            if idx % 2==0:
                pdf.set_fill_color(248, 249, 250)
            else:
                pdf.set_fill_color(255, 255, 255)
            
            for i, header_val in enumerate(headers):
                val=str(row.get(header_val.lower(), ''))
                pdf.cell(widths[i], h, val[:25], border=1, fill=True, align='L')
            pdf.ln()
        pdf_output=pdf.output()
        buffer=BytesIO(pdf_output)
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name="Leads_report.pdf",
            mimetype='application/pdf'
        )
    flash('Invalid format or export error.', 'leadserror')
    return redirect(url_for('leads'))
@app.route('/download-lead-template')
@login_required
def download_lead_template():
    template_path = 'static/templates/bulk_upload_lead_template.csv'
    return send_file(template_path, as_attachment=True, download_name='bulk_upload_lead_template.csv')

@app.route('/bulk-upload-leads', methods=['GET', 'POST'])
@login_required
def bulk_upload_leads():
    if request.method == 'POST':
        file = request.files.get('lead_file')
        if not file:
            flash('No file uploaded.', 'leadserror')
            return redirect(url_for('bulk_upload_leads'))
        try:
            df = pd.read_csv(file).fillna('')
            col_map = {c.lower(): c for c in df.columns}
            
            req_check = {'name', 'email', 'phone'}
            if not req_check.issubset(set(col_map.keys())):
                flash(f'Missing required columns: name, email, phone', 'leadserror')
                return redirect(url_for('bulk_upload_leads'))
            
            success_count = 0
            errors = []
            source_map = {e.value.lower(): e for e in LeadSource}
            status_map = {e.value.lower(): e for e in LeadStatus}
            
            for idx, row in df.iterrows():
                row_num = idx + 2
                def get_val(key):
                    c = col_map.get(key.lower())
                    return str(row[c]).strip() if c else ''

                name = get_val('name')
                email = get_val('email')
                phone_raw = get_val('phone')
                if phone_raw.endswith('.0'): phone_raw = phone_raw[:-2]
                phone_number = re.sub(r'\D', '', phone_raw)
                
                company = get_val('company')
                source_str = get_val('source').lower()
                status_str = get_val('status').lower()
                
                assigned_to_email = get_val('assigned_to')
                assigned_to_id = current_user.employee.id
                if assigned_to_email and assigned_to_email.lower() not in ['', 'nan', 'none']:
                    assigned_emp = Employee.query.join(User).filter(User.email == assigned_to_email).first()
                    if assigned_emp: assigned_to_id = assigned_emp.id

                if not all([name, email, phone_number]) or name.lower() == 'nan':
                    errors.append(f"Row {row_num}: Fields missing")
                    continue  
                if len(phone_number) != 10:
                    errors.append(f"Row {row_num}: Phone not 10 digits ({phone_number})")
                    continue  
                if Lead.query.filter_by(email=email, is_deleted=False).first():
                    errors.append(f"Row {row_num}: Email duplicate")
                    continue  
                if Lead.query.filter_by(phone_number=phone_number, is_deleted=False).first():
                    errors.append(f"Row {row_num}: Phone duplicate")
                    continue

                new_lead = Lead(
                    name=name,
                    email=email,
                    phone_number=phone_number,
                    company=company,
                    source=source_map.get(source_str, LeadSource.OTHER),
                    status=status_map.get(status_str, LeadStatus.NEW),
                    created_by=current_user.employee.id,
                    assigned_to=assigned_to_id
                )
                db.session.add(new_lead)
                success_count += 1
            
            if success_count > 0:
                db.session.commit()
                if errors:
                    msg = f"Imported {success_count}. Issues: " + ", ".join(errors[:3])
                    if len(errors) > 3: msg += "..."
                    flash(msg, 'leadssuccess')
                else:
                    flash(f'Successfully imported {success_count} leads!', 'leadssuccess')
                return redirect(url_for('leads'))
            else:
                if errors:
                    msg = "No leads imported. Issues: " + ", ".join(errors[:3])
                    if len(errors) > 3: msg += "..."
                    flash(msg, 'leadserror')
                return redirect(url_for('bulk_upload_leads'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing file: {str(e)}', 'leadserror')
            return redirect(url_for('bulk_upload_leads'))
    return render_template('Leads/bulkuploadleads.html')

@app.route('/convert-lead/<int:lead_id>')
@login_required
def convert_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    
    # Check if lead is already converted
    if lead.converted_customer:
        flash('This lead has already been converted to a customer.', 'leadserror')
        return redirect(url_for('leads'))
    
    # Validate if customer already exists (by email or phone)
    existing_customer = Customer.query.filter(
        (Customer.email == lead.email) | (Customer.phone_number == lead.phone_number)
    ).filter_by(is_deleted=False).first()
    
    if existing_customer:
        # If exists, we still link them? User said "first validate that customer is exist or not"
        # Usually we shouldn't create a duplicate. 
        # I'll inform the user and suggest linking or erroring.
        flash(f'Customer already exists with email {lead.email} or phone {lead.phone_number}.', 'leadserror')
        return redirect(url_for('leads'))
    
    try:
        # Create new Customer from Lead data
        new_customer = Customer(
            lead_id=lead.id,
            name=lead.name,
            email=lead.email,
            phone_number=lead.phone_number,
            address=lead.address,
            city=lead.city,
            company=lead.company,
            source=lead.source,
            status=CustomerStatus.NEW,
            notes=lead.notes,
            assigned_to=lead.assigned_to,
            created_by=current_user.employee.id,
            updated_by=current_user.employee.id
        )
        
        # Update Lead status
        lead.status = LeadStatus.ACTIVE
        
        db.session.add(new_customer)
        db.session.commit()
        
        flash(f'Successfully converted lead "{lead.name}" to an active customer!', 'leadssuccess')
        return redirect(url_for('customers'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error during conversion: {str(e)}', 'leadserror')
        return redirect(url_for('leads'))

if __name__ == '__main__':
    app.run(debug=True)