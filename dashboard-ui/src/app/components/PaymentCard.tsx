import { Copy } from "lucide-react";
import { PaymentResponse, PaymentStage } from "../types";

const STAGE_LABELS: Record<PaymentStage, string> = {
  created: "Создано",
  paid: "Оплачено",
  confirmed: "Подтверждено",
  key_issued: "Ключ выдан",
  expired: "Истекло",
};

export function PaymentCard({
  payment,
  paymentStage,
  onCopyCode,
  onOpenPay,
  onMarkPaid,
}: {
  payment: PaymentResponse;
  paymentStage: PaymentStage;
  onCopyCode: () => void;
  onOpenPay: () => void;
  onMarkPaid: () => void;
}) {
  return (
    <section className="panel">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-sm">
          Платеж <b>{payment.payment_code}</b>: {payment.amount_ton} TON (~{payment.amount_rub} ₽)
        </p>
        <button className="icon-btn" onClick={onCopyCode}>
          <Copy size={14} />
        </button>
      </div>
      <p className="text-xs text-white/60">Истекает: {payment.expires_at}</p>
      <div className="payment-steps mt-2">
        {(["created", "paid", "confirmed", "key_issued"] as PaymentStage[]).map((stage) => {
          const activeOrder = ["created", "paid", "confirmed", "key_issued"];
          const currentIdx = activeOrder.indexOf(paymentStage);
          const stepIdx = activeOrder.indexOf(stage);
          const active = currentIdx >= stepIdx && paymentStage !== "expired";
          return (
            <div key={stage} className={`payment-step ${active ? "payment-step-active" : ""}`}>
              {STAGE_LABELS[stage]}
            </div>
          );
        })}
      </div>
      <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <button className="primary-btn" onClick={onOpenPay}>
          Оплатить в Tonkeeper
        </button>
        <button className="secondary-btn" onClick={onMarkPaid}>
          Я оплатил
        </button>
      </div>
    </section>
  );
}
