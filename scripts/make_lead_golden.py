"""Genera el set de prueba de LeadScore: 30 consultas con su veredicto esperado.

Salida: samples/leadscore/leads.json (los leads crudos) y samples/leadscore/golden.json
(el veredicto esperado: tier, rango de score, códigos de motivo que deben aparecer y cuáles
no deben aparecer). Los leads duplicados llevan `duplicate_of` apuntando al caso original:
sirven para medir el dedupe, no para el score.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "samples" / "leadscore"

HOT, WARM, COLD = "HOT", "WARM", "COLD"

CASES = [
    # ---------------------------------------------------------------- calientes
    dict(id="L01", tier=HOT, lo=85, hi=100,
         must=["service_match", "urgency", "budget", "email_ok", "phone_ok", "message_detail"],
         lead=dict(name="Ana Perez", email="ana.perez@gmail.com", phone="+56 9 8123 4567",
                   source="formulario web",
                   message="Hola, me duele una muela desde ayer y necesito hora urgente. Tengo isapre, "
                           "puedo ir en la tarde despues de las 18:00 si hay cupo.")),
    dict(id="L02", tier=HOT, lo=70, hi=90,
         must=["service_match", "budget", "price_question", "email_ok", "phone_ok"],
         lead=dict(name="Rodrigo Silva", email="rsilva@empresa.cl", phone="912345678",
                   source="formulario web",
                   message="Necesito cotizar dos implantes. Quiero saber cuanto sale y si se puede pagar en cuotas.")),
    dict(id="L03", tier=HOT, lo=65, hi=85,
         must=["service_match", "price_question", "email_ok", "phone_ok", "time_given"],
         lead=dict(name="Camila Rojas", email="camila.rojas@outlook.com", phone="+56976543210",
                   source="instagram",
                   message="Hola! Quiero hacerme un blanqueamiento, cuanto sale? Puedo el sabado en la manana.")),
    dict(id="L04", tier=HOT, lo=70, hi=95,
         must=["service_match", "urgency", "returning", "email_ok", "phone_ok"],
         lead=dict(name="Pedro Soto", email="pedro.soto@gmail.com", phone="+56 9 5555 1234",
                   source="whatsapp",
                   message="Hola, ya fui paciente de ustedes. Me fractur\u00e9 un diente y necesito atenci\u00f3n hoy mismo.")),
    dict(id="L05", tier=HOT, lo=65, hi=90,
         must=["service_match", "budget", "email_ok", "phone_ok", "message_detail", "time_given"],
         lead=dict(name="Josefa Munoz", email="josefa.munoz@gmail.com", phone="+56966778899",
                   source="formulario web",
                   message="Quiero empezar ortodoncia con brackets. Tengo convenio con isapre y quisiera "
                           "saber los valores. Puedo ir despues de las 17 cualquier dia de la semana.")),
    # ---------------------------------------------------------------- tibios
    dict(id="L06", tier=WARM, lo=45, hi=69,
         must=["service_match", "price_question", "email_ok"],
         lead=dict(name="Beto Fuentes", email="beto.fuentes@gmail.com",
                   source="instagram", message="cuanto sale la limpieza dental?")),
    dict(id="L07", tier=WARM, lo=45, hi=69,
         must=["service_match", "email_ok", "phone_ok"],
         lead=dict(name="Maria Jose Tapia", email="mj.tapia@gmail.com", phone="+56 9 4321 8765",
                   source="formulario web",
                   message="Hola, quiero hacerme una limpieza y revisar unas caries que tengo.")),
    dict(id="L08", tier=WARM, lo=45, hi=69,
         must=["service_match", "email_ok", "message_detail"],
         lead=dict(name="Ignacio Vera", email="ignacio.vera@hotmail.com",
                   source="formulario web",
                   message="Buenas tardes, tengo una muela del juicio que me molesta hace semanas y quiero "
                           "saber si conviene sacarla. No tengo claro el costo.")),
    dict(id="L09", tier=WARM, lo=45, hi=69,
         must=["service_match", "phone_ok", "urgency"],
         lead=dict(name="Carolina Diaz", phone="+56 9 1234 5678",
                   source="whatsapp", message="Hola, me duele mucho una muela, es urgente, tienen hora?")),
    dict(id="L10", tier=WARM, lo=45, hi=69,
         must=["service_match", "price_question", "phone_ok", "time_given"],
         lead=dict(name="Felipe Aravena", phone="+56998765432",
                   source="whatsapp",
                   message="Buenas, quisiera cotizar una endodoncia. Puedo llamar en la manana.")),
    dict(id="L11", tier=WARM, lo=40, hi=69,
         must=["service_match", "email_ok"],
         lead=dict(name="Valentina Cruz", email="vale.cruz@gmail.com",
                   source="formulario web", message="Hola, quiero alineadores invisalign.")),
    dict(id="L12", tier=WARM, lo=40, hi=69,
         must=["service_match", "message_detail", "email_ok"],
         lead=dict(name="Sergio Pino", email="spino@correo.cl",
                   source="formulario web",
                   message="Mi hija de 8 a\u00f1os necesita atenci\u00f3n dental infantil, tiene una caries y "
                           "le da miedo el dentista. Quisiera saber c\u00f3mo trabajan con ni\u00f1os.")),
    dict(id="L13", tier=WARM, lo=45, hi=69,
         must=["service_match", "budget", "email_ok", "phone_ok"],
         lead=dict(name="Daniela Ortiz", email="daniela.ortiz@gmail.com", phone="+56 9 7766 5544",
                   source="formulario web",
                   message="Tengo fonasa, quiero saber si atienden con bonificaci\u00f3n para resinas.")),
    dict(id="L14", tier=WARM, lo=40, hi=69,
         must=["service_match", "email_ok", "phone_ok"],
         lead=dict(name="Matias Lagos", email="mlagos@gmail.com", phone="+56911223344",
                   source="instagram", message="Hola, hacen blanqueamiento? quiero hora")),
    dict(id="L15", tier=WARM, lo=45, hi=69,
         must=["service_match", "returning", "email_ok"],
         lead=dict(name="Paula Herrera", email="paula.herrera@gmail.com",
                   source="formulario web",
                   message="Soy paciente de la cl\u00ednica, quiero retomar mi tratamiento de periodoncia por las enc\u00edas.")),
    dict(id="L16", tier=WARM, lo=40, hi=69,
         must=["service_match", "price_question", "email_ok", "phone_ok"],
         lead=dict(name="Cristian Nunez", email="cnunez@gmail.com", phone="+56955443322",
                   source="formulario web", message="Valores de ortodoncia, por favor.")),
    # ---------------------------------------------------------------- frios
    dict(id="L17", tier=COLD, lo=0, hi=44,
         must=["email_ok"], absent=["service_match", "urgency"],
         lead=dict(name="Alvaro Mena", email="alvaro.mena@gmail.com",
                   source="formulario web", message="Hola, buenas tardes.")),
    dict(id="L18", tier=COLD, lo=0, hi=44,
         must=["email_ok"],
         lead=dict(name="Rocio Salas", email="rocio.salas@gmail.com",
                   source="instagram", message="info")),
    dict(id="L19", tier=COLD, lo=0, hi=44,
         must=["no_contact"],
         lead=dict(name="Anonimo", source="formulario web", message="Hola, quer\u00eda consultar algo.")),
    dict(id="L20", tier=COLD, lo=0, hi=44,
         must=["invalid_email"],
         lead=dict(name="Tomas Rivas", email="tomas.rivas@@gmail.com",
                   source="formulario web", message="hola quiero hora")),
    dict(id="L21", tier=COLD, lo=0, hi=44,
         must=["invalid_email"],
         lead=dict(name="Lead Prueba", email="prueba@mailinator.com",
                   source="formulario web", message="prueba de formulario")),
    dict(id="L22", tier=COLD, lo=0, hi=44,
         must=["no_contact"],
         lead=dict(source="instagram", message="precio?")),
    # ---------------------------------------------------------------- descartes
    dict(id="L23", tier=COLD, lo=0, hi=20,
         must=["spam"],
         lead=dict(name="Agencia SEO", email="ventas@agencia-seo.cl", phone="+56 2 2345 6789",
                   source="formulario web",
                   message="Ofrecemos posicionamiento web y marketing digital para cl\u00ednicas. "
                           "Queremos ser su socio comercial.")),
    dict(id="L24", tier=COLD, lo=0, hi=20,
         must=["spam"],
         lead=dict(name="Crypto Club", email="info@cryptoclub.io",
                   source="formulario web",
                   message="Ganaste un premio! Participa en nuestro sorteo de inversion en crypto.")),
    dict(id="L25", tier=COLD, lo=0, hi=20,
         must=["out_of_scope"],
         lead=dict(name="Juan Perez", email="juan.perez@gmail.com", phone="+56933334444",
                   source="formulario web",
                   message="Adjunto mi curriculum para una practica profesional en su cl\u00ednica.")),
    dict(id="L26", tier=COLD, lo=0, hi=20,
         must=["out_of_scope"],
         lead=dict(name="Proveedor Dental", email="ventas@insumosdental.cl",
                   source="formulario web",
                   message="Somos proveedor de insumos dentales, queremos enviarles nuestro catalogo.")),
    # ---------------------------------------------------------------- duplicados
    dict(id="L27", tier=HOT, lo=85, hi=100, duplicate_of="L01",
         must=["service_match"],
         lead=dict(name="Ana Perez", email="ANA.PEREZ@gmail.com", phone="+56 9 8123 4567",
                   source="whatsapp",
                   message="Hola, me duele una muela desde ayer y necesito hora urgente. Tengo isapre.")),
    dict(id="L28", tier=WARM, lo=40, hi=69, duplicate_of="L06",
         must=["service_match"],
         lead=dict(name="Beto Fuentes", email="Beto.Fuentes@gmail.com", phone="+56 9 8765 4321",
                   source="whatsapp", message="hola, cuanto sale la limpieza?")),
    dict(id="L29", tier=WARM, lo=40, hi=69, duplicate_of="L11",
         must=["service_match"],
         lead=dict(name="Valentina Cruz", email="vale.cruz@gmail.com ", source="instagram",
                   message="hola, sigo interesada en los alineadores")),
    dict(id="L30", tier=HOT, lo=65, hi=95, duplicate_of="L04",
         must=["service_match", "urgency"],
         lead=dict(name="Pedro Soto", email="pedro.soto@gmail.com", source="formulario web",
                   message="Hola de nuevo, sigo con el diente fracturado, necesito atenci\u00f3n urgente hoy.")),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    leads: list[dict] = []
    golden: list[dict] = []
    for c in CASES:
        lead = dict(c["lead"])
        lead["id"] = c["id"]
        if c.get("duplicate_of"):
            lead["duplicate_of"] = c["duplicate_of"]
        leads.append(lead)
        golden.append({
            "id": c["id"],
            "expect": {
                "tier": c["tier"],
                "score_min": c["lo"],
                "score_max": c["hi"],
                "codes": c.get("must", []),
                "absent": c.get("absent", []),
            },
        })
    (OUT / "leads.json").write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "golden.json").write_text(json.dumps(golden, ensure_ascii=False, indent=2), encoding="utf-8")
    tiers = {}
    for c in CASES:
        tiers[c["tier"]] = tiers.get(c["tier"], 0) + 1
    print(f"30 casos -> {OUT}  {tiers}")


if __name__ == "__main__":
    main()
