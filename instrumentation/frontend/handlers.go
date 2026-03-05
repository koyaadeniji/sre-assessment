package main

// These functions wrap the existing frontend handlers to add custom spans.
// In the original Online Boutique source (src/frontend/handlers.go),
// add the tracer.Start calls shown here inside the existing handler functions.

import (
	"net/http"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
)

// productHandler — add this span inside the existing productHandler function,
// around the template rendering call.
func instrumentedProductRender(w http.ResponseWriter, r *http.Request, product Product, recommendations []Product, currency string) error {
	ctx := r.Context()

	ctx, span := tracer.Start(ctx, "render-product-page",
		trace.WithAttributes(
			attribute.String("product.id", product.Id),
			attribute.String("product.name", product.Name),
			attribute.String("user.currency", currency),
			attribute.Int("product.count", len(recommendations)),
		),
	)
	defer span.End()

	err := templates.ExecuteTemplate(w, "product", map[string]interface{}{
		"product":         product,
		"recommendations": recommendations,
		"currency":        currency,
	})
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "template render failed")
	}

	return err
}

// placeOrderHandler — add this span inside the existing placeOrderHandler,
// around the form parsing and validation logic.
func instrumentedCheckoutForm(r *http.Request) error {
	ctx := r.Context()

	_, span := tracer.Start(ctx, "process-checkout-form",
		trace.WithAttributes(
			attribute.String("session.id", sessionID(r)),
		),
	)
	defer span.End()

	if err := r.ParseForm(); err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "form parse failed")
		return err
	}

	span.SetAttributes(
		attribute.String("checkout.email", r.FormValue("email")),
		attribute.String("checkout.zip_code", r.FormValue("zip_code")),
		attribute.String("checkout.country", r.FormValue("country")),
	)

	return nil
}
