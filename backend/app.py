from flask import Flask, request, jsonify, render_template

app = Flask(__name__)


# =========================================================
# COMPANY API
# =========================================================

@app.route('/create_company', methods=['POST'])
def create_company():

    data = request.get_json()

   

    company_name = data.get('company_name')
    industry = data.get('industry')
    company_size = data.get('company_size')
    company_type = data.get('company_type')


    company_email = data.get('company_email')
    company_phone = data.get('company_phone')
    company_website = data.get('company_website')


    country = data.get('country')
    state = data.get('state')
    city = data.get('city')
    company_address = data.get('company_address')
    postal_code = data.get('postal_code')

   

    if not company_name:
        return jsonify({
            "error": "Company name is required"
        }), 400

    if not industry:
        return jsonify({
            "error": "Industry is required"
        }), 400

    if not company_size:
        return jsonify({
            "error": "Company size is required"
        }), 400

    if not company_type:
        return jsonify({
            "error": "Company type is required"
        }), 400

    if not company_email:
        return jsonify({
            "error": "Company email is required"
        }), 400

    if not company_phone:
        return jsonify({
            "error": "Company phone is required"
        }), 400

    if not country:
        return jsonify({
            "error": "Country is required"
        }), 400

    if not state:
        return jsonify({
            "error": "State is required"
        }), 400

    if not city:
        return jsonify({
            "error": "City is required"
        }), 400

    if not company_address:
        return jsonify({
            "error": "Company address is required"
        }), 400

    if not postal_code:
        return jsonify({
            "error": "Postal code is required"
        }), 400

    # =====================================================
    # TEMPORARY PRINT
    # =====================================================

    print("Company:", company_name)
    print("Industry:", industry)
    print("Company Size:", company_size)
    print("Company Type:", company_type)

    print("Email:", company_email)
    print("Phone:", company_phone)
    print("Website:", company_website)

    print("Country:", country)
    print("State:", state)
    print("City:", city)
    print("Address:", company_address)
    print("Postal Code:", postal_code)

    # =====================================================
    # RESPONSE
    # =====================================================

    return jsonify({
        "message": "Company created successfully",

        "company": {
            "name": company_name,
            "industry": industry,
            "size": company_size,
            "type": company_type,

            "email": company_email,
            "phone": company_phone,
            "website": company_website,

            "country": country,
            "state": state,
            "city": city,
            "address": company_address,
            "postal_code": postal_code
        }
    }), 201


# =========================================================
# COMPANY UI
# =========================================================

@app.route('/company', methods=['GET'])
def company_page():

    return render_template('company.html')


# =========================================================
# DEPARTMENT API
# =========================================================

@app.route('/departments', methods=['POST'])
def create_department():

    data = request.get_json()

    department_name = data.get('department_name')
    department_head = data.get('department_head')
    department_status = data.get(
        'department_status',
        'active'
    )

    # =====================================================
    # VALIDATION
    # =====================================================

    if not department_name:
        return jsonify({
            "error": "Department name is required"
        }), 400

    # =====================================================
    # TEMPORARY PRINT
    # =====================================================

    print("Department:", department_name)
    print("Department Head:", department_head)
    print("Department Status:", department_status)

    # =====================================================
    # RESPONSE
    # =====================================================

    return jsonify({

        "message": "Department created successfully",

        "department": {
            "name": department_name,
            "head": department_head,
            "status": department_status
        }

    }), 201


# =========================================================
# ORGANIZATION UI
# =========================================================

@app.route('/organization', methods=['GET'])
def organization_page():

    return render_template('organization.html')


# =========================================================
# HOME
# =========================================================

@app.route('/')
def home():

    return """
        <h1>HRMS</h1>

        <p>Welcome to HRMS</p>

        <a href="/company">
            Create Company
        </a>
    """


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == '__main__':

    app.run(
        debug=True
    )