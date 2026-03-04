import { BadgeHelp } from "lucide-react";
import { BootstrapResponse, FaqResponse } from "../../types";

export function SupportTab({
  bootstrap,
  faq,
  onOpenLink,
}: {
  bootstrap: BootstrapResponse;
  faq: FaqResponse["items"];
  onOpenLink: (url: string) => void;
}) {
  return (
    <>
      <section className="panel">
        <h2 className="section-title">РџРѕРґРґРµСЂР¶РєР°</h2>
        <p className="text-sm text-white/65">FAQ Рё Р±С‹СЃС‚СЂС‹Р№ РїРµСЂРµС…РѕРґ РІ С‡Р°С‚ РїРѕРґРґРµСЂР¶РєРё.</p>
        <button className="primary-btn mt-3 w-full" onClick={() => onOpenLink(bootstrap.links.support)}>
          РќР°РїРёСЃР°С‚СЊ РІ РїРѕРґРґРµСЂР¶РєСѓ
        </button>
      </section>

      <section className="panel">
        <div className="space-y-2">
          {faq.map((item) => (
            <div key={item.q} className="faq-row">
              <div className="mt-0.5 text-emerald-300">
                <BadgeHelp size={16} />
              </div>
              <div>
                <p className="text-sm font-medium">{item.q}</p>
                <p className="text-xs text-white/65">{item.a}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
