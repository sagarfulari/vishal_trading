from flask import Flask, render_template, request, url_for, redirect, flash, send_from_directory, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import func
from flask_login import login_user, LoginManager, login_required, current_user, logout_user
from num2words import num2words
from datetime import datetime
from db import db, Invoice, User, Customer
from billing import GetInvoice, Customers, Report, Stocks


app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'


#Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

# CREATE DATABASE
class Base(DeclarativeBase):
    pass

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'


#Tables creation code added in db.py
db.init_app(app)

with app.app_context():
    db.create_all()

#Converting number to words
def num_to_words(num):
    num_str = str(num)
    if len(num_str) >= 6:
        val1 = num_str[0:len(num_str)-5]
        num_in_words = num2words(int(val1))+ " lakh "
        val2 = num_str[len(num_str)-5:len(num_str)]
        if val2 == "00000":
            pass
        else:
            num_in_words += num2words(int(val2))
    else:
        num_in_words = num2words(num)

    return num_in_words + " only"


@app.route('/', methods=["GET", "POST"])
def home():
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')

        response = db.session.execute(db.select(User).where(User.email == email))
        user = response.scalar()
        # Email doesn't exist or password incorrect.
        if not user:
            flash("Email does not exist, please Register.")
            return redirect(url_for('home'))
        elif not check_password_hash(user.password, password):
            flash('Password incorrect, please try again.')
            return redirect(url_for('home'))
        else:
            login_user(user)
            return redirect(url_for('secrets'))

    return render_template("login.html", logged_in=current_user.is_authenticated)



@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":

        email = request.form.get('email')
        response = db.session.execute(db.select(User).where(User.email == email))

        # Note, email in db is unique so will only have one result.
        user = response.scalar()
        if user:
            # User already exists
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('home'))

        hash_and_salted_password = generate_password_hash(
            request.form.get('password'),
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            email=request.form.get('email'),
            password=hash_and_salted_password,
            name=request.form.get('name'),
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("secrets"))

    return render_template("register.html", logged_in=current_user.is_authenticated)


@app.route('/home')
@login_required
def secrets():
    # print(current_user.name)
    daily_tins_count = Stocks.get_all_daily_stocks()
    print(daily_tins_count)
    stock = Stocks.get_stock()
    print(stock.other)
    search = request.args.get('search')
    response = GetInvoice.get_all_invoices()
    invoices = []
    more_than_ten_days = []
    no_of_days = []
    today = datetime.today()
    for invoice in response:
        if invoice.total_amount['status'] == "pending":
            invoices.append(invoice)
            days_diff = (today.date() - invoice.date).days

            if days_diff >= 10:
                more_than_ten_days.append(invoice)
                no_of_days.append(days_diff)
    print(more_than_ten_days)
    print(no_of_days)
    zipped_data = zip(more_than_ten_days, no_of_days)



    return render_template("home.html", name=current_user.name, logged_in=True, invoices=invoices, search=search, stock=stock, daily_tins_count=daily_tins_count, card="pending", more_than_ten_days=more_than_ten_days, no_of_days=no_of_days, zipped_data=zipped_data)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))



result = ""
list1 = []
customer_data = {}
totals = {}
@app.route("/billing", methods=["GET", "POST"])
@login_required
def billing():
    global customer_data
    # names = db.session.query(Customer).all()
    names = Customers.get_all_customers()
    response = GetInvoice.get_all_invoices()
    # invoice_no = 0
    if not response:
        invoice_no = 1
    else:
        invoice_no = db.session.query(func.max(Invoice.invoice_no)).scalar() + 1
    customer_data = {
        "invoice_no": invoice_no
    }
    if request.method == "POST":
        todays_date = f"{datetime.now().day}/{datetime.now().month}/{datetime.now().year}"
        action = request.form.get('action')

        if action == "add_goods":
            tin = request.form.get("tins")
            quantity = request.form.get("quantity")
            price = request.form.get("price")

            if quantity == "":
                # Customer_details
                customer_name = request.form.get("cust_name")
                cust_gst = request.form.get("gstin")
                eway_bill_no = request.form.get("eway_bill")
                invoice_no = request.form.get("invoice_no")
                customer_data = {
                    "customer_name": customer_name,
                    "cust_gst": cust_gst,
                    "eway_bill": eway_bill_no,
                    "invoice_no": invoice_no
                }
            else:
                if price == "":
                    price = 0
                total = int(quantity) * int(price)
                amount = round(total/1.05, 2)
                sgst = round(amount * 0.025, 2)

                new_data = {
                    "description" : tin,
                    "quantity": quantity,
                    "price": price,
                    "total": total,
                    "sgst": sgst,
                    "cgst": sgst,
                    "amount": amount,
                }
                list1.append(new_data)

                # Customer_details
                customer_name = request.form.get("cust_name")
                cust_gst = request.form.get("gstin")
                eway_bill_no = request.form.get("eway_bill")
                invoice_no = request.form.get("invoice_no")

                customer_data = {
                    "customer_name": customer_name,
                    "cust_gst": cust_gst,
                    "eway_bill": eway_bill_no,
                    "invoice_no": invoice_no
                }


            return render_template('billing.html', logged_in=True, show_second_form=True, dicts=list1, date=todays_date,
                                   customer_data=customer_data, names=names)
        elif action == "add_customer":
            customer_name = request.form.get("cust_name")
            eway_bill_no = request.form.get("eway_bill")
            cust_gst = request.form.get("gstin")
            if cust_gst == "":
                flash("Please enter GST Number")
            else:
                response = Customers.add_customer(customer_name, cust_gst)
                customer_data = {
                    "customer_name": customer_name,
                    "cust_gst": cust_gst,
                    "eway_bill": eway_bill_no,
                    "invoice_no": invoice_no
                }
            return render_template('billing.html', logged_in=True, show_second_form=True, dicts=list1, date=todays_date,
                                   customer_data=customer_data, names=names)


    return render_template('billing.html', logged_in=True, customer_data=customer_data, names=names)


@app.route("/delete_entry")
def delete_entry():
    idx = request.args.get("idx")
    print(idx)
    if len(list1) == 0:
        return redirect(url_for('billing'))
    elif len(list1) == 1:
        list1.pop(int(idx))
        return redirect(url_for('billing'))
    else:
        list1.pop(int(idx))
        return render_template('billing.html', logged_in=True, show_second_form=True, dicts=list1, customer_data=customer_data)


@app.route("/print", methods=["GET", "POST"])
def preview():
    global customer_data, totals, result
    todays_date = f"{datetime.now().day}/{datetime.now().month}/{datetime.now().year}"
    total_quantity = 0
    total_sgst = 0.0
    total_amount = 0.0
    overall_amount = 0
    for data in list1:
        total_quantity += int(data['quantity'])
        total_sgst += float(data['sgst'])
        total_amount += float(data['amount'])
        overall_amount += int(data['total'])
    amnt_in_words = num_to_words(overall_amount)
    totals = {
        "total_quantity": total_quantity,
        "total_sgst": round(total_sgst,2),
        "total_amount": round(total_amount, 2),
        "overall_amount": overall_amount,
        "amnt_in_words": amnt_in_words,
        "status": "pending"
    }
    return render_template("pdf_preview.html", bill_details=list1, data=customer_data, totals=totals, amt_in_words=amnt_in_words, date=todays_date, preview="show")


@app.route("/save_entry")
def save_entry():
    global result, list1, totals
    result = GetInvoice.save_invoice(customer_data=customer_data, goods_details=list1, total_amount=totals)
    if result == "Data saved successfully!":
        list1 = []
        totals = {}
        result = ""
        return redirect(url_for('secrets'))
    else:
        return redirect(url_for('preview'))

#Get GST no on select of customer name
@app.route('/get_gst', methods=['POST'])
def get_gst():
    data = request.json
    name = data.get('customer_name')  # Get the selected name from the request
    customer = Customer.query.filter_by(customer_name=name).first()
    if customer:
        return jsonify({'gst': customer.gst_no})  # Return the GST value
    return jsonify({'error': 'Customer not found'}), 404


#Show Invoice details
@app.route("/invoice/<int:invoice_no>", methods=["GET", "POST"])
def invoice_details(invoice_no):
    result = db.session.execute(db.select(Invoice).where(Invoice.invoice_no == invoice_no))
    invoice = result.scalar()

    return render_template("pdf_preview.html", bill_details=invoice.goods_details, data=invoice.customer_details, totals=invoice.total_amount,
                           amt_in_words=invoice.total_amount['amnt_in_words'], date=invoice.date)


@app.route("/update/<int:invoice_no>", methods=["GET", "POST"])
def update_invoice(invoice_no):
    daily_tins_count = Stocks.get_all_daily_stocks()
    stock = Stocks.get_stock()
    edit = request.args.get("edit")
    response = GetInvoice.get_all_invoices()
    all_invoices = []
    for invoice in response:
        if invoice.total_amount['status'] == "pending":
            all_invoices.append(invoice)
    if request.method == "POST":
        response = GetInvoice.update_invoice(invoice_no, request.form.get("name"), request.form.get("amount"), request.form.get("status"))
        response = db.session.execute(db.select(Invoice).where(Invoice.invoice_no == invoice_no))
        invoice = response.scalar()
        total = invoice.total_amount['overall_amount']
        invoices_list = [invoice]
        return render_template("home.html", name=current_user.name, logged_in=True, invoices=all_invoices, search="yes", invoices_list=invoices_list, stock=stock, daily_tins_count=daily_tins_count, total=total)

    if edit == "clear":
        response = GetInvoice.update_invoice(invoice_no, "", "", "clear")
        return redirect(url_for('secrets'))
    elif edit == "detail":
        response = db.session.execute(db.select(Invoice).where(Invoice.invoice_no == invoice_no))
        invoice = response.scalar()
        return render_template("home.html", edit="detail", invoice=invoice, logged_in=True, invoices=all_invoices, stock=stock, daily_tins_count=daily_tins_count)
    return redirect(url_for('secrets'))

@app.route("/home/search", methods=["GET", "POST"])
@login_required
def search():
    daily_tins_count = Stocks.get_all_daily_stocks()
    stock = Stocks.get_stock()
    response = GetInvoice.get_all_invoices()
    all_invoices = []
    for invoice in response:
        if invoice.total_amount['status'] == "pending":
            all_invoices.append(invoice)
    user_input = request.form.get("search")

    def check_input(item, response):
        invoices = []
        # Check if it's a number (integer)
        try:
            num = int(item)
            inv_detail = GetInvoice.get_invoice_details(num)
            invoices.append(inv_detail)
            total = inv_detail.total_amount['overall_amount']
            print(total)
            return invoices, total
        except ValueError:
            pass  # Not a number
        # Check if it's a date in the format DD/MM/YYYY
        try:
            date_obj = datetime.strptime(item, "%d/%m/%Y")
            # response = GetInvoice.get_all_invoices()
            # invoices = []
            total = 0
            for invoice in response:
                if invoice.date == date_obj.date():
                    total = total + int(invoice.total_amount['overall_amount'])
                    invoices.append(invoice)
            return invoices, total
        except ValueError:
            pass  # Not a date in the given format
        # If not a number or a date, it's treated as a string
        # response = GetInvoice.get_all_invoices()
        # invoices = []
        total = 0
        for invoice in response:

            if invoice.customer_details['customer_name'] == item:
                invoices.append(invoice)
                total = total + int(invoice.total_amount['overall_amount'])
                print(total)
        return invoices, total


    invoices_list, total = check_input(user_input, response)
    print(total)
    print(invoices_list)
    return render_template("home.html", name=current_user.name, logged_in=True, invoices=all_invoices, search="yes", invoices_list=invoices_list, stock=stock, daily_tins_count=daily_tins_count, total=total)




@app.route("/home/report", methods=["GET", "POST"])
@login_required
def report():
    report_of = request.args.get("reports")
    search = request.form.get("search")
    month = datetime.today().date().strftime("%B")
    if search:
        if search == "jan":
            month = "January"
        elif search == "feb":
            month = "February"
        elif search == "mar":
            month = "March"
        elif search == "apr":
            month = "April"
        elif search == "may":
            month = "May"
        elif search == "june":
            month = "June"
        elif search == "july":
            month = "July"
        elif search == "aug":
            month = "August"
        elif search == "sep":
            month = "September"
        elif search == "oct":
            month = "October"
        elif search == "nov":
            month = "November"
        elif search == "dec":
            month = "December"
        else:
            month = search.title()

    names = Customers.get_all_customers()
    if report_of == "six_month":
        missed_cust_list = []
        chart_html, cust_list, totals, months = Report.six_month_report()
        for month in range(len(months)):
            cust_missed = []
            for name in names:
                if name not in cust_list[month]:
                    cust_missed.append(name)
            missed_cust_list.append(cust_missed)
        return render_template("report.html", logged_in=True, chart=chart_html, cust_list=cust_list, totals=totals, months=months, missed_cust_list=missed_cust_list)


    chart_html, cust_list, totals, months, total_oil, monthly_invoices = Report.monthly_report(month)
    missed_cust_list = []
    for month in range(len(months)):
        cust_missed = []
        for name in names:
            if name not in cust_list[month]:
                cust_missed.append(name)
        missed_cust_list.append(cust_missed)

    return render_template("report.html", logged_in=True, chart=chart_html, cust_list=cust_list, totals=totals, months=months, missed_cust_list=missed_cust_list, total_oil=total_oil, monthly_invoices=monthly_invoices, monthly="monthly")



@app.route('/products', methods=["GET", "POST"])
@login_required
def products():
    daily_tins_count = Stocks.get_all_daily_stocks()
    stock = Stocks.get_stock()
    if request.method == "POST":
        action = request.form.get('action')
        if action == "add_packed_tins":
            if request.form.get("15KG") == "":
                RP15KG = 0
            else:
                RP15KG = request.form.get("15KG")
            if request.form.get("15LTR") == "":
                RP15LTR = 0
            else:
                RP15LTR = request.form.get("15LTR")
            if request.form.get("14_5KG") == "":
                RP14_5KG = 0
            else:
                RP14_5KG = request.form.get("14_5KG")
            if request.form.get("13KG") == "":
                RP13KG = 0
            else:
                RP13KG = request.form.get("13KG")
            available_tins = {
                "15KG": RP15KG,
                "15LTR": RP15LTR,
                "14_5KG": RP14_5KG,
                "13KG": RP13KG
            }
            Stocks.update_available_tins(available_tins, "add")
            return redirect(url_for("secrets"))

        else:
            if request.form.get("new_stock") == "0" and request.form.get("tins") == "0":
                Stocks.update_stock(float(request.form.get("new_stock")), int(request.form.get("tins")), "clear")
                return redirect(url_for('products'))
            elif request.form.get("new_stock") != "" and request.form.get("tins") != "":
                Stocks.update_stock(float(request.form.get("new_stock")), int(request.form.get("tins")), "add")
                return redirect(url_for('products'))
            elif request.form.get("new_stock") != "":
                Stocks.update_stock(float(request.form.get("new_stock")), 0, "add")
                return redirect(url_for('products'))
            elif request.form.get("tins") != "":
                Stocks.update_stock(0, int(request.form.get("tins")), "add")
                return redirect(url_for('products'))
            else:
                print("both not available")
                return redirect(url_for('products'))

    return render_template("products.html", name=current_user.name, logged_in=True, stock=stock, daily_tins_count=daily_tins_count)




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)