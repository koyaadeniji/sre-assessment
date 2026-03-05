#!/bin/bash
# =================================================================
# Traffic Generator for Distributed Trace Validation
# =================================================================
#
# This script exercises the full checkout flow to generate
# end-to-end distributed traces across all instrumented services.
#
# Usage: ./scripts/generate-traffic.sh [FRONTEND_URL]
#
# The generated traces should show:
# - frontend → productcatalog (browse products)
# - frontend → cart (add to cart)
# - frontend → checkout → payment (complete purchase)
# - frontend → recommendation (product suggestions)
#
# After running, check Kibana → APM → Traces for the full waterfall.
# =================================================================

set -e

FRONTEND_URL="${1:-http://localhost:8080}"
ITERATIONS="${2:-5}"

echo "========================================="
echo "  SRE Assessment — Traffic Generator"
echo "========================================="
echo "Target: $FRONTEND_URL"
echo "Iterations: $ITERATIONS"
echo ""

# check if the frontend is reachable
echo "[*] Checking frontend connectivity..."
if ! curl -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL" | grep -q "200"; then
    echo "[!] Frontend not reachable at $FRONTEND_URL"
    echo "    If using minikube: minikube service frontend-external -n online-boutique --url"
    echo "    Or: kubectl port-forward svc/frontend -n online-boutique 8080:80"
    exit 1
fi
echo "[+] Frontend is up!"
echo ""

for i in $(seq 1 $ITERATIONS); do
    echo "--- Iteration $i of $ITERATIONS ---"

    # step 1: browse the homepage (hits frontend + productcatalog + recommendation + ad)
    echo "  [1/5] Browsing homepage..."
    curl -s -o /dev/null -w "  HTTP %{http_code} (%{time_total}s)\n" "$FRONTEND_URL/"

    # step 2: view a product (hits frontend + productcatalog + recommendation)
    PRODUCT_ID="OLJCESPC7Z"  # vintage typewriter
    echo "  [2/5] Viewing product $PRODUCT_ID..."
    curl -s -o /dev/null -w "  HTTP %{http_code} (%{time_total}s)\n" "$FRONTEND_URL/product/$PRODUCT_ID"

    # step 3: add to cart (hits frontend + cart + recommendation)
    echo "  [3/5] Adding product to cart..."
    curl -s -o /dev/null -w "  HTTP %{http_code} (%{time_total}s)\n" \
        -X POST "$FRONTEND_URL/cart" \
        -d "product_id=$PRODUCT_ID&quantity=2"

    # step 4: view cart page
    echo "  [4/5] Viewing cart..."
    curl -s -o /dev/null -w "  HTTP %{http_code} (%{time_total}s)\n" "$FRONTEND_URL/cart"

    # step 5: checkout (hits frontend + checkout + payment + shipping + email + currency)
    # this is the big one — generates the deepest trace spanning most services
    echo "  [5/5] Placing order (checkout flow)..."
    curl -s -o /dev/null -w "  HTTP %{http_code} (%{time_total}s)\n" \
        -X POST "$FRONTEND_URL/cart/checkout" \
        -d "email=test@example.com" \
        -d "street_address=123+Test+St" \
        -d "zip_code=10001" \
        -d "city=New+York" \
        -d "state=NY" \
        -d "country=US" \
        -d "credit_card_number=4432801561520454" \
        -d "credit_card_expiration_month=03" \
        -d "credit_card_expiration_year=2028" \
        -d "credit_card_cvv=672"

    echo ""

    # small delay between iterations so traces don't overlap
    if [ $i -lt $ITERATIONS ]; then
        sleep 2
    fi
done

echo "========================================="
echo "  Traffic generation complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Open Kibana → Observability → APM → Traces"
echo "  2. Filter by service: frontend"
echo "  3. Look for 'POST /cart/checkout' transactions"
echo "  4. Click one to see the full distributed trace waterfall"
echo "  5. Check the Service Map for the full dependency graph"
echo ""
echo "  For error traces:"
echo "  - Try an expired card: credit_card_expiration_year=2020"
echo "  - Check Kibana APM → Errors tab for the recorded exception"
