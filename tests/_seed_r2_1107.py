"""The 20-note notebook round 2 of the 2026-11-07 composer audit was driven on
(tables, a numbered list, a checklist, accented names, one-word notes). The
clock is `TODAY`; every question runs through `composer.compose` with no model."""

from __future__ import annotations

from datetime import date

from tessellate.ai import composer

TODAY = date(2026, 11, 7)

raw=[
("Shopping","| Item | Price |\n|---|---|\n| Milk | £1.20 |\n| Bread | £2.50 |\n| Cheese | £4.00 |",58),
("Tokyo trip","Flights cost $900 return, leaving 3 April. Staying in Shinjuku for six nights.",40),
("Packing for Tokyo","1. passport\n2. rail pass\n3. adapter\n4. umbrella",39),
("Lisbon trip","Flights cost $420 return, leaving 12 May. Staying at Hotel Alfama near the river. Day trip to Sintra on the Thursday.",30),
("Lisbon packing list","- [x] Passport\n- [ ] Charger\n- [ ] Sunscreen\n- [ ] Walking shoes",20),
("Lisbon dinner","Remember to book a table for dinner in Lisbon on the first night.",25),
("coriander","I do not like coriander.",50),
("José García","José is my landlord. Phone 020 7946 0999. He fixes the boiler.",45),
("Jokes","Why did the scarecrow win an award? He was outstanding in his field.",44),
("Budget","Rent £950 a month\nGroceries £60 a week\nPhone £12\nGym £30",43),
("Bank","Sort code 12-34-56\nOverdraft limit £500",42),
("Car","MOT due 15 December\nService cost £210",41),
("Todo","- [ ] Book MOT\n- [x] Pay council tax\n- [ ] Email landlord\n- [ ] Buy stamps",36),
("Dentist","Phone 020 7946 0011\nDentist check-up on 11 November.",35),
("Dentist bill","Paid £85 for the check-up.",34),
("Running log","Ran 6 km on 25 October.",24),
("hi","hi",10),("milk","milk",11),
("Zoë's recital","Zoë plays on 21 November at 6pm at the Wigmore Hall.",33),
("Anna","Anna is my cousin. Her birthday is 9 August.",32),
("Tom","Tom is my friend.",31),
]
notes=[]
for i,(t,b,d) in enumerate(raw,1):
    dd=date.fromordinal(TODAY.toordinal()-d)
    notes.append({"id":i,"content":t+"\n"+b if b!=t else t,"category":"Uncategorised","tags":[],"created_at":dd.isoformat()+"T10:00:00Z"})


def ask(question: str, only: tuple[str, ...] | None = None, history: list | None = None) -> str:
    """The composed answer to `question` over the seed (or only the notes titled in `only`)."""
    pool = [n for n in notes if only is None or n["content"].split("\n", 1)[0] in only]
    return composer.compose(question, pool, today=TODAY, **({"history": history} if history else {}))["text"]
