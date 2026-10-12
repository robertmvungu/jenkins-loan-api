"""Loan Quote API - a tiny Flask service used to practise Jenkins CI/CD."""
import os

from flask import Flask, jsonify, request


def monthly_payment(principal: float, annual_rate: float, months: int) -> float:
    """Standard amortised loan instalment, rounded to 2 decimals."""
    if principal <= 0:
        raise ValueError("principal must be greater than 0")
    if months <= 0:
        raise ValueError("months must be greater than 0")
    if annual_rate < 0:
        raise ValueError("annual_rate cannot be negative")

    r = annual_rate / 100 / 12
    if r == 0:
        return round(principal / months, 2)
    return round(principal * r / (1 - (1 + r) ** -months), 2)


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify(status="ok", version=os.getenv("APP_VERSION", "dev"))

    @app.post("/api/v1/quote")
    def quote():
        data = request.get_json(silent=True) or {}
        try:
            principal = float(data["principal"])
            annual_rate = float(data["annual_rate"])
            months = int(data["months"])
            instalment = monthly_payment(principal, annual_rate, months)
        except KeyError as exc:
            return jsonify(error=f"missing field: {exc.args[0]}"), 400
        except (TypeError, ValueError) as exc:
            return jsonify(error=str(exc)), 400

        total = round(instalment * months, 2)
        return jsonify(
            monthly_payment=instalment,
            total_payable=total,
            total_interest=round(total - principal, 2),
        )

    return app


app = create_app()

if __name__ == "__main__":  # local dev only; containers use gunicorn
    app.run(host="127.0.0.1", port=5000)
