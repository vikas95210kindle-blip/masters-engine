# Dukaan Desk

A single-page seller desk for starting on Indian marketplaces with about ₹10,000.
Kept separate from the masters engine; nothing in `engine/`, `config/` or `data/` is touched.

Live page: https://claude.ai/artifact/Xi29MfRT3goFCGbM5sWp7m (private to the owner until shared).
Source: `dukaan-desk.html`.

| Tab | Replaces |
| --- | --- |
| Start plan | – (tonight / this week / weeks 2–4 / later checklist) |
| Find products | 100 starter ideas + CSV imports from Helium 10 / Jungle Scout / SellerSprite, ranked 0–100 on ten weighted checks, with a per-product breakdown, research brief (Claude, or a prompt for Gemini/ChatGPT) and a thumbs-up to choose |
| Price check | Profit per order after commission, fixed fee, shipping, GST, ads and returns |
| ₹10k planner | Budget split and the orders needed for ₹10k / ₹25k / ₹50k profit |
| Stock & orders | Unicommerce / Browntape at low volume |
| Sourcing | Where to buy (IndiaMART, Udaan, TradeIndia, wholesale hubs, Alibaba), import landed-cost calculator, quote log |
| Launch kit | For thumbs-up products: launch steps, packaging and volumetric weight, HSN/GST, GST invoice PDF, hand-off to pricing, listing and stock |
| Label cropper | PDF croppers (runs in the browser with pdf.js + pdf-lib) |
| Listing writer | ChatGPT / Gemini step |
| Tools & channels | Notes on every tool in the original list |

No marketplace fee, rate or rule is hard-coded as fact: fees are entered from the seller
panel, and the defaults in Price check are labelled as an example. The desk does not scrape
or log in to any marketplace.

Starter ideas carry only judgement fields (weight class, breakable, licence flag, season,
source hint), labelled *Estimate*. Demand, competition, rating, margin and price score zero
until real data is imported or entered, so an unmeasured idea cannot outrank a measured one
on guesswork.
