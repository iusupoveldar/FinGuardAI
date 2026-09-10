# Script to generate syntetic data

# Goal: 1000 customers, 10000 transactions

# Good Examples:
"""
    coffee
    salary
    rent
    shopping
    steam
"""
# Suspicious Examples:
"""
    multiple same amount transfers ($3000)
    foreign transfers
    new recipients
    rapid movement
"""

transaction = {
    "customer":23,
    "amount":9800,
    "type":"wire",
    "country":"Turkey"
}
