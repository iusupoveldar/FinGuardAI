# Tasks

# Frontend

## Dashboard

Show: Customer List(Name, Rist Score, Status)


## Customer Page

Show: Customer Profile(Age, Country, Account Age, Risk Level, Transactions, Date, Amount, Merchant, Country, Type)


# Backend
## Get /customers

## Get /customers/{id}/transactions

## Post /investigate/{custromer_id}

This will call "Transaction Analysis" -> "RAG retrival" -> "Deepseek" or any other LLM


# AI
## Button "Investigation" -> Output: Summary, Risk factors, Evidence, Relevant AML rules, Recommended next steps, Sources

# ML
include docs/architecture-decisions.md

# Database

## Database Design
## Table: Cusatomers
    * id
    * name
    * country
    * occupation
    * account_created
    * risk_score

## Table: Transactions
    * id
    * customer_id
    * date
    * amount
    * currency
    * merchant
    * country
    * transcation_type

## Table: Documents (RAG)
    * id
    * title
    * source
    * text
    * embedding

