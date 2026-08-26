import api from "./client";

/* =========================================================
   PAYMENT ORDER
   ========================================================= */

export async function createPaymentOrder({
  product = "monte_carlo",
}) {
  const response = await api.post("/payments/order", {
    product,
  });

  return response.data;
}

/* =========================================================
   PAYMENT VERIFICATION
   ========================================================= */

export async function verifyPayment({
  razorpay_order_id,
  razorpay_payment_id,
  razorpay_signature,
}) {
  const response = await api.post("/payments/verify", {
    razorpay_order_id,
    razorpay_payment_id,
    razorpay_signature,
  });

  return response.data;
}
