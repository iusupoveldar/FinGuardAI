def calculate_customer_risk(customer):
    risk_score = 0
    if customer.country.lower() != "canada":
        risk_score += 20
    return risk_score