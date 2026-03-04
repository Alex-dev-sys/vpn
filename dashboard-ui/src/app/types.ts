export type TabKey = "store" | "setup" | "profile" | "support";

export type BootstrapResponse = {
  user: {
    telegram_id: number;
    username: string | null;
    balance_ton: number;
    referrals_count: number;
    ref_link: string;
  };
  status: {
    vpn_active: boolean;
    dns_active: boolean;
    active_until: string | null;
    state: "online" | "offline";
  };
  prices: {
    rate_rub_per_ton: number;
    plans: Array<{
      code: "vpn" | "dns" | "pro";
      title: string;
      subtitle: string;
      price_rub: number;
      price_ton: number;
    }>;
  };
  links: {
    bot: string;
    p2p: string;
    support: string;
  };
  install: {
    vpn_keys: Array<{ key_id: number; access_url: string; expires_at: string }>;
    dns: Array<{ access_id: number; dns_server_ip: string; current_ip: string | null; expires_at: string }>;
  };
};

export type FaqResponse = { items: Array<{ q: string; a: string }> };

export type AuthFallback = {
  title: string;
  description: string;
  bot_link: string;
};

export type PaymentResponse = {
  payment_code: string;
  amount_ton: number;
  amount_rub: number;
  expires_at: string;
  ton_link: string;
  bot_check_link: string;
};

export type PaymentStage = "created" | "paid" | "confirmed" | "key_issued" | "expired";

export type PaymentStatusResponse = {
  payment_code: string;
  status: string;
  stage: PaymentStage;
  is_final: boolean;
  expires_at: string;
};

export type PaymentConfirmResponse = {
  payment_code: string;
  status: string;
  stage: PaymentStage;
  is_final: boolean;
  verified: boolean;
  message?: string;
};

export type P2PQuoteResponse = {
  amount_ton: number;
  amount_rub: number;
  rate_rub_per_ton: number;
  margin_percent: number;
  max_available_ton: number;
  remaining_daily_rub: number;
};

export type P2POrderResponse = {
  order_id: number;
  status: string;
  amount_ton: number;
  amount_rub: number;
  wallet_masked: string;
  payment_requisites: {
    bank: string;
    card: string;
    sbp_phone?: string | null;
  };
};

export type P2POrderStatusResponse = {
  order_id: number;
  status: string;
  stage: "created" | "paid" | "processing" | "completed" | "canceled";
  is_final: boolean;
  amount_ton: number;
  amount_rub: number;
  tx_hash?: string | null;
  tx_link?: string | null;
  cancel_reason?: string | null;
};

export type TelegramWebApp = {
  ready: () => void;
  expand: () => void;
  openLink?: (url: string) => void;
  initData?: string;
  initDataUnsafe?: { user?: { id?: number } };
};
