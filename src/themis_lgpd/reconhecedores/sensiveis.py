"""Reconhecedores de dados pessoais sensíveis, de intimidade, de menores e de quase-identificadores.

Abrangem os dados sensíveis do art. 5º, II, da LGPD (saúde, convicção religiosa, opinião política,
filiação sindical, vida sexual, dado genético ou biométrico, origem racial ou étnica), as
informações relativas à intimidade e à vida privada protegidas pelo art. 31 da LAI (violência,
situação de risco) e os dados de crianças e adolescentes (art. 14 da LGPD).

As regras se dividem em duas camadas, tratadas de forma diferente pelos perfis:

``contextual``
    Frases que já descrevem a situação de uma pessoa ("diagnosticado com…", "vítima de violência
    doméstica", "CID F41.1"). São tarjadas no perfil LAI.
``semantica``
    Termos isolados ("asma", "católico", "homossexual"). São tarjados apenas quando a frase se
    refere a uma pessoa determinada; caso contrário, são sinalizados para revisão. Assim, "a
    política de saúde mental prevê atendimento para depressão", conteúdo de interesse público, não
    é tarjado.
"""

from __future__ import annotations

from importlib import resources

import regex as re

from ..texto import dobrar
from .base import CONTEXTUAL, SEMANTICA, Padrao, ReconhecedorPadroes


def _termos(*t: str) -> str:
    """Alternativa entre termos, delimitada por fronteiras de palavra."""
    return r"\b(?:" + "|".join(t) + r")\b"


_VARIANTES = {"a": "[aáâã]", "e": "[eéê]", "i": "[ií]", "o": "[oóôõ]", "u": "[uúü]", "c": "[cç]"}


def _sem_acento(termo: str) -> str:
    """Expressão que aceita o termo com ou sem acentos e com qualquer espaçamento entre as palavras."""
    return r"\s+".join("".join(_VARIANTES.get(c, re.escape(c)) for c in p) for p in dobrar(termo).split())


def _medicamentos() -> str:
    """Alternativa com os medicamentos de ``dados/medicamentos.txt``, dos nomes mais longos aos mais curtos."""
    texto = resources.files("themis_lgpd.dados").joinpath("medicamentos.txt").read_text(encoding="utf-8")
    nomes = {linha.strip() for linha in texto.splitlines() if linha.strip() and not linha.startswith("#")}
    return "|".join(_sem_acento(n) for n in sorted(nomes, key=len, reverse=True))


# --------------------------------------------------------------------------- Saúde
#: Doenças, condições, deficiências, tratamentos e procedimentos de saúde. Cada item é uma expressão
#: regular; variações de gênero, número e acentuação estão incluídas na própria expressão.
DOENCAS = (
    r"asm[áa]tic[oa]s?", r"asma(?:\s+cr[ôo]nica)?", r"diabetes(?:\s+(?:tipo\s+[12]|mellitus))?", r"diab[ée]tic[oa]s?",
    r"hipertens[ãa]o(?:\s+arterial)?", r"hipertens[oa]s?", r"c[âa]ncer(?:\s+de\s+\w+)?", r"neoplasia(?:\s+maligna)?",
    r"tumor(?:es)?(?:\s+maligno)?", r"leucemia", r"linfoma", r"met[áa]stase", r"(?:adeno)?carcinomas?", r"melanoma",
    r"hiv", r"aids", r"soropositiv[oa]", r"sida", r"hepatites?(?:\s+[a-e])?", r"tuberculose", r"hansen[íi]ase",
    r"s[íi]filis", r"hpv", r"gonorreia", r"herpes", r"covid(?:-?19)?", r"dengue", r"zika", r"chikungunya",
    r"mal[áa]ria(?:\s+(?:vivax|falciparum))?", r"esclerose\s+(?:m[úu]ltipla|lateral\s+amiotr[óo]fica)", r"parkinson", r"alzheimer",
    r"dem[êe]ncia", r"epilepsia", r"epil[ée]ptic[oa]s?", r"convuls[õo]es", r"avc", r"acidente\s+vascular\s+cerebral",
    r"infarto(?:\s+agudo)?(?:\s+do\s+mioc[áa]rdio)?", r"insufici[êe]ncia\s+(?:renal|card[íi]aca|respirat[óo]ria|hep[áa]tica)", r"cirrose",
    r"cardiopatia", r"arritmias?(?:\s+card[íi]aca)?", r"trombose", r"embolia", r"aneurisma", r"l[úu]pus", r"fibromialgia",
    r"artrite(?:\s+reumatoide)?", r"artrose", r"h[ée]rnia\s+de\s+disco", r"doen[çc]a\s+de\s+\w+",
    r"s[íi]ndrome\s+de\s+\w+", r"s[íi]ndrome\s+do\s+p[âa]nico", r"autismo", r"autista", r"tea", r"tdah",
    r"transtorno\s+(?:do\s+espectro\s+autista|bipolar|obsessivo[- ]compulsivo|de\s+ansiedade|depressivo|mental|"
    r"de\s+personalidade|alimentar|de\s+estresse\s+p[óo]s-traum[áa]tico)", r"transtornos\s+mentais(?:\s+e\s+comportamentais)?",
    r"transtornos?\s+emocionais", r"depress[ãa]o", r"depressiv[oa]", r"ansiedade\s+generalizada", r"bipolaridade",
    r"esquizofrenia", r"esquizofr[êe]nic[oa]", r"psicose", r"burnout", r"esgotamento\s+(?:profissional|mental)",
    r"anorexia", r"bulimia", r"obesidade(?:\s+m[óo]rbida)?", r"depend[êe]ncia\s+qu[íi]mica", r"alcoolismo",
    r"alco[óo]latra", r"dependente\s+qu[íi]mic[oa]", r"tabagismo", r"paraplegi[ao]", r"tetraplegi[ao]",
    r"cadeirantes?", r"deficiente\s+(?:visual|auditiv[oa]|f[íi]sic[oa]|intelectual)",
    # Enumeração dos tipos ("deficiência física, visual ou auditiva") tarjada inteira.
    r"defici[êe]ncias?\s+(?:visua(?:l|is)|auditivas?|f[íi]sicas?|intelectua(?:l|is)|mental|mentais|m[úu]ltiplas?|motoras?)"
    r"(?:\s*(?:,|\be\b|\bou\b)\s*(?:visual|auditiva|f[íi]sica|intelectual|mental|m[úu]ltipla|motora|sensorial))*",
    r"surdez", r"cegueira",
    r"surd[oa]", r"ceg[oa]", r"pcd", r"amputa[çc][ãa]o", r"amputad[oa]", r"gravidez\s+de\s+risco",
    r"aborto", r"gestante", r"gr[áa]vida", r"infertilidade", r"endometriose", r"menopausa", r"osteoporose",
    r"glaucoma", r"catarata", r"retinopatia", r"queimaduras?\s+de\s+\w+\s+grau", r"intoxica[çc][ãa]o(?:\s+agud[oa])?(?:\s+(?:alimentar|por\s+[\w-]+(?:\s+de\s+[\w-]+)?))?",
    r"hemodi[áa]lise", r"di[áa]lise", r"quimioterapia", r"radioterapia", r"transplante",
    r"mastectomia", r"histerectomia", r"bari[áa]trica", r"tratamento\s+(?:psiqui[áa]trico|psicol[óo]gico|oncol[óo]gico|"
    r"antirretroviral|hormonal)", r"f[áa]rmacos?\s+(?:hormonais|controlados|psiqui[áa]tricos)",
    r"antidepressivos?", r"ansiol[íi]ticos?", r"antipsic[óo]ticos?", r"insulinas?(?:\s+(?:glargina|nph|regular|asparte|lispro|detemir|degludeca|humana|an[áa]loga))?", r"internad[oa]",
    r"interna[çc](?:[ãa]o|[õo]es)(?:\s+(?:psiqui[áa]tricas?|hospitalar(?:es)?))?", r"internamentos?", r"uti", r"coma", r"sequelas?", r"crise\s+(?:de\s+)?(?:ansiedade|"
    r"p[âa]nico|convulsiva|epil[ée]ptica)", r"traumatismo(?:\s+craniano)?", r"fraturas?(?:\s+expostas?)?(?:\s+(?:de|d[oa]|n[oa])\s+\w+)?",
    r"condi[çc][ãa]o\s+(?:de\s+sa[úu]de|cl[íi]nica|m[ée]dica)(?:\s+pr[ée]-?existente)?", r"grupo\s+de\s+risco",
    r"comorbidades?", r"doen[çc]as?\s+(?:pr[ée]-?existentes?|cr[ôo]nicas?|raras?|graves?)",
    r"enfermidade(?:\s+(?:respirat[óo]ria|cr[ôo]nica|grave|rara))*", r"(?:pessoa|crian[çc]a|aluno|aluna|filh[oa])\s+com\s+"
    r"defici[êe]ncia", r"doen[çc]a\s+de\s+crohn", r"crohn", r"covid", r"surto\s+(?:psic[óo]tico|de\s+\w+)",
    r"transtorno\s+de\s+p[âa]nico", r"pr[óo]teses?", r"[óo]rteses?", r"fisioterapia", r"medicamentos?\s+controlados?",
    # "cirurgia de vesícula"; o tipo ("cirurgia ortopédica") vem dos qualificadores de _TIPO_CLINICO, e
    # não qualquer palavra seguinte ("cirurgia que", "cirurgias mensais").
    r"bi[óo]psia", r"cirurgias?(?:\s+(?:d[eoa]|n[oa])\s+(?!(?:minha|meu|sua|seu|um|uma|ele|ela)\b)\w+)?",
    r"per[íi]cia\s+m[ée]dica", r"hospitalizad[oa]", r"exame\s+de\s+sangue",
    r"tratamento\s+(?:hospitalar|m[ée]dico|quimioter[áa]pico|radioter[áa]pico|cl[íi]nico|odontol[óo]gico)",
    # Doenças e condições
    r"fibrose\s+c[íi]stica", r"paralisia\s+(?:cerebral|infantil|facial)", r"hiperplasia\s+prost[áa]tica(?:\s+benigna)?",
    r"periodontite", r"leptospirose", r"febre\s+(?:amarela|maculosa|reum[áa]tica)", r"leishmaniose(?:\s+visceral)?",
    r"esquistossomose", r"toxoplasmose", r"meningite", r"sarampo", r"influenza", r"srag", r"brucelose(?:\s+humana)?",
    r"hipopituitarismo", r"hipotireoidismo", r"hipertireoidismo", r"enfisema(?:\s+pulmonar)?", r"dpoc", r"pneumonia",
    r"bronquite", r"crise\s+hipertensiva", r"anemia(?:\s+falciforme)?", r"doen[çc]a\s+falciforme", r"hemofilia",
    r"talassemia", r"atrofia\s+muscular\s+espinhal", r"distrofia\s+muscular", r"microcefalia", r"hidrocefalia",
    r"psor[íi]ase", r"vitiligo", r"dermatite\s+at[óo]pica", r"dermatites?", r"doen[çc]a\s+cel[íi]aca", r"pancreatite", r"apendicite",
    r"labirintite", r"enxaqueca", r"apneia\s+(?:obstrutiva\s+)?do\s+sono", r"sepse",
    r"infec[çc](?:[ãa]o|[õo]es)\s+(?:intestina(?:l|is)|urin[áa]rias?|hospitalar(?:es)?|generalizadas?|virais|viral|bacterianas?|"
    r"f[úu]ngicas?|respirat[óo]rias?|pulmonar(?:es)?|renal|renais|de\s+urina|(?:por|pel[oa])\s+[\w-]+)",
    r"n[óo]dulos?\s+(?:na|no)\s+\w+(?:\s+(?:direit[oa]|esquerd[oa]))?",
    r"ruptura\s+(?:total\s+|parcial\s+)?d[oe]\s+(?:ligamento|tend[ãa]o|menisco)(?:\s+\w+){0,2}",
    r"les[õo]es\s+por\s+esfor[çc]o\s+repetitivo", r"ler\s*/\s*dort", r"doen[çc]as?\s+autoimunes?",
    r"condi[çc][õo]es\s+autoimunes", r"passou\s+mal",
    # Saúde reprodutiva
    r"laqueaduras?(?:\s+tub[áa]ria)?", r"vasectomias?", r"esteriliza[çc][ãa]o\s+(?:volunt[áa]ria|cir[úu]rgica)",
    r"dispositivo\s+intrauterino", r"diu(?:\s+(?:de\s+cobre|hormonal))?", r"implantes?\s+(?:subd[ée]rmicos?|contraceptivos?|hormonais?)",
    r"pr[ée]-?natal", r"fertiliza[çc][ãa]o\s+in\s+vitro", r"reprodu[çc][ãa]o\s+assistida",
    # Procedimentos e exames
    r"colecistectomias?(?:\s+videolaparosc[óo]pica|\s+por\s+videolaparoscopia)?", r"apendicectomia", r"prostatectomia",
    r"tireoidectomia", r"artroplastias?(?:\s+(?:total|parcial))?(?:\s+d[eo]\s+\w+)?", r"angioplastia", r"cateterismo", r"marca-?passo", r"ponte\s+de\s+safena",
    r"(?:procedimento|cirurgia)\s+videolaparosc[óo]pic[oa]", r"videolaparoscopia", r"densitometria\s+[óo]ssea",
    r"mamografia", r"colonoscopia", r"endoscopia", r"resson[âa]ncia\s+magn[ée]tica",
    r"tomografia(?:\s+(?:computadorizada|de\s+coer[êe]ncia\s+[óo]ptica))?", r"ecocardiograma", r"eletrocardiograma",
    r"mapeamento\s+de\s+retina", r"exame\s+de\s+toque(?:\s+retal)?",
    r"exames?\s+de\s+(?:urina|fezes|imagem|vista|pr[óo]stata|mama)", r"tonometria", r"facoemulsifica[çc][ãa]o",
    r"ultrassonografias?", r"hemogramas?", r"papanicolau", r"audiometria", r"espirometria", r"eletroencefalograma",
    r"cintilografia", r"teste\s+ergom[ée]trico", r"mamografias", r"colonoscopias", r"endoscopias",
    r"endodontia", r"tratamento\s+de\s+canal", r"extra[çc][ãa]o\s+dent[áa]ria", r"implantes?\s+(?:dent[áa]rios?|coclear(?:es)?)",
    r"retirada\s+d[aeo]\s+(?:ves[íi]cula|tireoide|[úu]tero|mama|ap[êe]ndice|ba[çc]o|rim|pr[óo]stata|tumor|n[óo]dulo)",
    r"inser[çc][ãa]o\s+de\s+diu", r"transfus[ãa]o\s+de\s+sangue", r"psicoterapia", r"terapia\s+ocupacional",
    r"acompanhamento\s+(?:psicol[óo]gico|psiqui[áa]trico|psicoterap[êe]utico|nutricional|fonoaudiol[óo]gico|"
    r"multiprofissional)", r"(?:consultas?|acompanhamento|atendimento|tratamento)\s+(?:de|em|para)\s+sa[úu]de\s+mental",
    r"tratamento\s+(?:imunossupressor|dial[íi]tico|paliativo|fisioter[áa]pico|ortod[ôo]ntico)",
    # Aparelho digestivo
    r"gastrites?", r"colelit[íi]ase", r"colecistite", r"c[áa]lculos?\s+(?:biliar(?:es)?|renais|renal)",
    r"pedras?\s+n[ao]s?\s+(?:ves[íi]cula|rins?)", r"diverticulite", r"gastroenterite", r"retocolite", r"colite",
    r"refluxo\s+gastroesof[áa]gico", r"[úu]lceras?(?:\s+(?:g[áa]stricas?|duodena(?:l|is)|p[ée]pticas?|venosas?|varicosas?|"
    r"de\s+press[ãa]o))?", r"hemorroidas", r"h[ée]rnias?\s+(?:inguina(?:l|is)|umbilica(?:l|is)|abdomina(?:l|is)|de\s+hiato)",
    r"diarreias?", r"v[ôo]mitos?", r"parasitoses?", r"verminoses?", r"ameb[íi]ase", r"giard[íi]ase", r"salmonelose",
    r"esteatose(?:\s+hep[áa]tica)?",
    # Aparelho respiratório e doenças do trabalho
    r"rinite", r"sinusite", r"bronquites", r"bronquiolite", r"silicose", r"pneumoconiose", r"asbestose", r"coqueluche",
    r"falta\s+de\s+ar", r"crises?\s+(?:asm[áa]ticas?|respirat[óo]rias?|al[ée]rgicas?|renais|de\s+(?:asma|enxaqueca|tosse))",
    r"les(?:[ãa]o|[õo]es)\s+por\s+esfor[çc]os?\s+repetitivos?", r"dort", r"tendinites?", r"bursite", r"tenossinovite",
    r"epicondilite", r"s[íi]ndrome\s+do\s+t[úu]nel\s+do\s+carpo", r"lombalgia", r"cervicalgia", r"dorsalgia", r"ciatalgia",
    r"lombociatalgia", r"escoliose", r"osteoartrite", r"entorse", r"luxa[çc][ãa]o", r"espondilite(?:\s+anquilosante)?",
    # Condições descritas de forma genérica ("problemas respiratórios", "problema de saúde")
    r"problemas?\s+(?:graves?\s+|s[ée]rios?\s+)?(?:respirat[óo]rios?|card[íi]acos?|renais|neurol[óo]gicos?|psicol[óo]gicos?|"
    r"psiqui[áa]tricos?|emociona(?:l|is)|de\s+ordem\s+(?:emocional|psicol[óo]gica|psiqui[áa]trica)|"
    r"de\s+(?:vis[ãa]o|audi[çc][ãa]o|cora[çc][ãa]o|coluna|press[ãa]o|tireoide|sa[úu]de(?!\s+p[úu]blica)(?:\s+mental)?))"
    r"(?:\s+recorrentes?|\s+cr[ôo]nicos?)?",
    r"doen[çc]as?\s+(?:respirat[óo]rias?|ocupaciona(?:l|is)|cardiovasculares?|card[íi]acas?|renais|renal|"
    r"neurodegenerativas?|infecciosas?|sexualmente\s+transmiss[íi]ve(?:l|is))", r"mol[ée]stias?\s+graves?",
    r"pacientes?\s+cr[ôo]nicos?", r"mal\s+s[úu]bito", r"desmaios?", r"convuls[ãa]o", r"tonturas?", r"vertigens?",
    r"dores?\s+(?:fortes?|cr[ôo]nicas?|intensas?|constantes?|agudas?|lombar(?:es)?|abdomina(?:l|is)|tor[áa]cicas?|"
    r"no\s+peito|de\s+cabe[çc]a|nas?\s+costas|nas?\s+articula[çc][õo]es)", r"sangramentos?", r"hemorragias?",
    r"febre\s+(?:alta|persistente)", r"ferimentos?(?:\s+(?:leves?|graves?))?",
    # "complicações" só com o qualificador clínico que a segue ("complicações respiratórias")
    r"complica[çc](?:[ãa]o|[õo]es)(?=\s+(?:respirat|card[íi]ac|rena|neurol[óo]gic|p[óo]s-operat))",
    # Sistema nervoso, circulação e sangue
    r"neuropatias?", r"polineuropatia", r"neuralgia", r"cefaleia", r"miastenia(?:\s+gravis)?", r"distonia", r"espasticidade",
    r"press[ãa]o\s+(?:arterial\s+)?(?:alta|elevada)", r"colesterol\s+alto", r"hipercolesterolemia", r"dislipidemia",
    r"pr[ée]-?diabetes", r"miocardiopatias?", r"cardiomiopatias?", r"angina", r"varizes",
    r"fator(?:es)?\s+(?:viii|ix|vii|xiii)", r"imunoglobulinas?", r"tipo\s+sangu[íi]neo",
    r"(?<=\bsangue\s|\bsangu[íi]neo\s)(?-i:AB|A|B|O)\s+(?:positivo|negativo)",
    # Visão e audição
    r"perda\s+(?:da\s+|de\s+)?(?:vis[ãa]o|audi[çc][ãa]o|auditiva|visual)", r"baixa\s+(?:vis[ãa]o|acuidade\s+visual)",
    r"perdendo\s+a\s+(?:vis[ãa]o|audi[çc][ãa]o)", r"vis[ãa]o\s+(?:piorou|turva|monocular|subnormal)", r"ceratocone",
    r"estrabismo", r"degenera[çc][ãa]o\s+macular", r"descolamento\s+de\s+retina", r"aparelhos?\s+auditivos?",
    # Alergias, intolerâncias e reações
    r"alergias?(?:\s+(?:a|à|ao|aos|às|de)\s+[\w-]+(?:\s+d[eoa]s?\s+[\w-]+){0,3})?", r"al[ée]rgic[oa]s?", r"aplv",
    r"intoler[âa]ncias?(?:\s+(?:severa|grave|leve))?\s+(?:a|à|ao)\s+(?:lactose|gl[úu]ten|frutose|prote[íi]na\s+do\s+leite"
    r"(?:\s+de\s+vaca)?)(?:\s+e\s+(?:à\s+|ao\s+|a\s+)?(?:lactose|gl[úu]ten|frutose))?",
    r"rea[çc](?:[ãa]o|[õo]es)\s+(?:al[ée]rgicas?|adversas?|anafil[áa]ticas?)", r"choque\s+anafil[áa]tico", r"anafilaxia",
    # Infecções
    r"septicemia", r"staphylococcus(?:\s+aureus)?", r"estafiloc[óo]cic[oa]", r"klebsiella(?:\s+pneumoniae)?",
    r"superbact[ée]rias?", r"bact[ée]rias?\s+multirresistentes?", r"varicela", r"catapora", r"caxumba", r"rub[ée]ola",
    r"escabiose", r"micoses?", r"candid[íi]ase", r"pediculose", r"t[ée]tano", r"difteria", r"poliomielite", r"gripe",
    r"h1n1", r"mpox", r"var[íi]ola(?:\s+dos\s+macacos)?",
    r"monkeypox", r"htlv", r"citomegalov[íi]rus", r"herpes[- ]zoster", r"conjuntivite", r"otites?",
    r"infec[çc](?:[ãa]o|[õo]es)\s+sexualmente\s+transmiss[íi]ve(?:l|is)", r"(?-i:IST|DST)s?",
    # Oncologia
    r"sarcoma", r"mieloma(?:\s+m[úu]ltiplo)?", r"glioblastoma", r"glioma", r"neoplasias", r"cistos?", r"miomas?",
    # Sistema nervoso e saúde mental (complementos)
    r"derrame(?:\s+cerebral)?(?!\s+de\b)", r"acidente\s+vascular\s+encef[áa]lico", r"hemiplegia",
    r"hemiparesia", r"les[ãa]o\s+medular", r"dislexia", r"discalculia", r"ins[ôo]nia", r"fadiga\s+cr[ôo]nica",
    r"transtornos?\s+(?:afetivo\s+bipolar|opositor\s+desafiador|d[eo]\s+d[ée]ficit\s+de\s+aten[çc][ãa]o(?:\s+(?:e|com)\s+"
    r"hiperatividade)?|de\s+(?:humor|aprendizagem|conduta|compuls[ãa]o\s+alimentar)|do\s+sono|psic[óo]tico|"
    r"esquizoafetivo|dissociativo)",
    r"consultas?\s+(?:com|no|na|d[eo])\s+(?:o\s+|a\s+)?(?:psiquiatra|psic[óo]log[oa]|oncologista|infectologista|neurologista|"
    r"cardiologista|endocrinologista|nefrologista|reumatologista|hematologista|urologista|mastologista|ortopedista|"
    r"oftalmologista|gastroenterologista|pneumologista|dermatologista)",
    # Saúde da mulher, do homem e da criança
    r"s[íi]ndrome\s+dos\s+ov[áa]rios\s+polic[íi]sticos", r"ov[áa]rios?\s+polic[íi]sticos?", r"disfun[çc][ãa]o\s+er[ée]til",
    r"parto\s+(?:normal|ces[áa]reo|prematuro|humanizado|natural)", r"fenda\s+palatina", r"l[áa]bio\s+leporino",
    r"icter[íi]cia(?:\s+neonatal)?",
    # Olhos, pele, boca e sangue
    r"pter[íi]gio", r"uve[íi]te", r"miopia", r"astigmatismo", r"hipermetropia", r"queimaduras?", r"c[áa]ries?",
    r"gengivite", r"aparelho\s+ortod[ôo]ntico", r"trombocitopenia", r"plaquetopenia",
    # Lesões, dependência de cuidados e terapias
    r"les(?:[ãa]o|[õo]es)\s+(?:n[oa]s?|d[oa]s?)\s+(?:joelhos?|ombros?|coluna|tornozelos?|punhos?|quadril|m[ãa]os?|p[ée]s?|"
    r"cotovelos?|menisco|ligamento|tend[ãa]o|cabe[çc]a|c[ée]rebro|medula)",
    r"acamad[oa]s?", r"oxig[êe]nio\s+domiciliar", r"cuidados\s+paliativos", r"rem[ée]dios?\s+controlados?",
    r"(?:cannabis|canabis|maconha)\s+medicinal", r"[óo]leo\s+de\s+(?:cannabis|canabidiol)",
    # Saúde mental e dependência química
    r"(?<!\bcom\s)ansiedade", r"estresse\s+(?:p[óo]s-traum[áa]tico|cr[ôo]nico|ocupacional)",
    r"depend[êe]ncia\s+(?:alco[óo]lica|de\s+(?:[áa]lcool|drogas|crack|coca[íi]na|opioides?|subst[âa]ncias\s+psicoativas))",
    r"drogadi[çc][ãa]o", r"uso\s+abusivo\s+de\s+(?:[áa]lcool|drogas|subst[âa]ncias)",
    # Nutrição e doenças metabólicas raras
    r"desnutri[çc][ãa]o", r"subnutri[çc][ãa]o", r"fenilceton[úu]ria", r"erros?\s+inatos?\s+do\s+metabolismo",
    r"restri[çc](?:[ãa]o|[õo]es)\s+alimentar(?:es)?", r"f[óo]rmulas?\s+(?:nutricionais|metab[óo]licas)(?:\s+especiais)?",
    r"(?:nutri[çc][ãa]o|dietas?)\s+(?:enterais?|parenterais?|enteral|parenteral)", r"mucopolissacaridose",
    r"acondroplasia", r"osteog[êe]nese\s+imperfeita", r"nanismo",
    # Deficiência e mobilidade: "deficiência" isolada só após "com" ou "de" ("criança com deficiência"),
    # e não seguida de complemento ("deficiência no atendimento" não é dado de saúde).
    r"(?<=\bcom\s|\bde\s)defici[êe]ncias?(?!\s+(?:n[oa]s?|d[eoa]s?|em)\b)", r"mobilidade\s+reduzida",
    r"limita[çc](?:[ãa]o|[õo]es)\s+(?:de\s+mobilidade|f[íi]sicas?|motoras?)", r"necessidades\s+especiais",
    r"cadeiras?\s+de\s+rodas", r"muletas",
    # Gestação e parto
    r"gesta[çc][ãa]o(?:\s+(?:de\s+alto\s+)?risco|\s+gemelar)?", r"gravidez", r"gestantes", r"ces[áa]rea", r"cesariana",
    r"puerp[ée]rio", r"pu[ée]rpera", r"(?:pr[ée]-?)?ecl[âa]mpsia", r"prematuridade",
    # Dispositivos e cuidados domiciliares
    r"cpap", r"bipap", r"oxigenoterapia", r"concentrador(?:es)?\s+de\s+oxig[êe]nio", r"colostomia", r"ileostomia",
    r"traqueostomia", r"gastrostomia", r"ostomias?", r"bolsas?\s+de\s+colostomia",
    r"sondas?\s+(?:vesica(?:l|is)|nasog[áa]strica|uretra(?:l|is)|de\s+al[íi]vio)",
    # Imunização: vacina contra doença determinada ou nome de vacina
    # (vacinas veterinárias, como a da febre aftosa, não são dado de saúde de pessoa)
    r"vacina(?:s|[çc][ãa]o)?\s+(?:contra\s+(?:a\s+|o\s+)?|de\s+)(?!febre\s+aftosa|raiva\s+animal)[\w-]+",
    r"imuniza[çc][ãa]o\s+contra\s+(?:a\s+|o\s+)?[\w-]+",
    r"(?:vacina\s+)?(?:bivalente|pentavalente|hexavalente|tetraviral|tr[íi]plice\s+viral|coronavac)",
    # Classes de medicamentos
    r"antibi[óo]ticos?", r"anti-?inflamat[óo]rios?", r"analg[ée]sicos?", r"anticonvulsivantes?", r"anticoagulantes?",
    r"imunossupressor(?:es)?", r"corticoides?", r"corticoster[óo]ides?", r"broncodilatador(?:es)?",
    r"anti-?hipertensivos?", r"hipoglicemiantes?", r"antirretrovira(?:l|is)", r"quimioter[áa]picos?", r"col[íi]rios?",
    r"imunobiol[óo]gicos?",
    # Classificação Internacional de Doenças citada sem código
    r"(?:c[óo]digo|classifica[çc][ãa]o)\s+internacional\s+de\s+doen[çc]as", r"(?-i:CID)(?:-?1[01])?",
    # Benefícios e medicamentos que revelam a condição
    r"aux[íi]lio[- ]doen[çc]a", r"aposentadoria\s+por\s+invalidez", r"benef[íi]cio\s+por\s+incapacidade",
    r"medicamentos?\s+(?:biol[óo]gicos?|de\s+alto\s+custo|imunobiol[óo]gicos?)",
    # Especialidades: "consulta de oncologia" revela a condição tanto quanto o diagnóstico
    r"oncologia", r"ortopedia", r"cardiologia", r"neurologia", r"psiquiatria", r"endocrinologia", r"nefrologia",
    r"reumatologia", r"hematologia", r"infectologia", r"urologia", r"oftalmologia", r"gastroenterologia",
    r"pneumologia", r"mastologia", r"proctologia", r"otorrinolaringologia",
)

#: Código da CID-10 ("F41.1", "G40") ou da CID-11 ("6A70.1", "BA00"; sem as letras I e O).
_CODIGO_CID = (r"(?:(?-i:[1-9A-HJ-NP-Z][A-HJ-NP-Z]\d[0-9A-HJ-NP-Z](?:\.[0-9A-HJ-NP-Z]{1,2})?)|"
               r"[A-Z]-?\d{2}(?:\.\d{1,2})?)\b")

#: Regras de saúde que descrevem a condição de uma pessoa.
SAUDE_CONTEXTUAL = [
    # Código da CID-10 ou CID-11 com o rótulo "CID" e, opcionalmente, a descrição que o acompanha.
    # Também "C.I.D." e listas de códigos ("CID F32.1, F41.1 e G40").
    Padrao("SAUDE", r"\b(?:CID|C\.I\.D\.?)(?:[\s-]?1[01])?\s*[:\-]?\s*" + _CODIGO_CID
           + rf"(?:\s*(?:,|;|/|\be\b|\bou\b)\s*{_CODIGO_CID})*" + r"(?:\s*[-–]\s*[^\n.;,]{3,60})?", 0.95,
           camada=CONTEXTUAL, nome="saude:cid"),
    # Expressão de diagnóstico, tratamento ou afastamento seguida da condição.
    Padrao("SAUDE",
           # "portadores" (plural) designa um grupo ("benefício para portadores de deficiência"): fica
           # para a regra de termo isolado, que só tarja com vínculo a pessoa determinada.
           r"\b(?:diagn[óo]stico\s+(?:de|confirmado\s+de)|diagnosticad[oa]s?\s+com|portador(?:a)?\s+de|"
           r"acometid[oa]\s+(?:de|por)|sofre\s+de|sofro\s+de|tem\s+(?:um\s+)?(?:quadro|hist[óo]rico)\s+de|"
           r"em\s+tratamento\s+(?:de|para|contra)|faz\s+tratamento\s+(?:de|para)|tratando\s+(?:de|um)|"
           r"laudo\s+(?:que\s+)?(?:atesta|indica|comprova)|afastad[oa]\s+por|licen[çc]a\s+(?:m[ée]dica\s+)?(?:por|para\s+tratamento\s+de))"
           r"\s+[^\n.;,()]{3,60}", 0.9, camada=CONTEXTUAL, nome="saude:frase"),
    # Código da CID sem o rótulo ("F41.1"): exige vocabulário médico próximo, pois o formato se
    # confunde com outros códigos. Os códigos iniciados por U, de uso especial, não são considerados.
    Padrao("SAUDE", r"\(?\b[A-TV-Z]\d{2}\.\d\b\)?", 0.6, camada=SEMANTICA, ignorar_caixa=False,
           contexto=("cid", "diagn[óo]stico", "laudo", "atestado", "m[ée]dic[oa]", "doen[çc]a", "afastamento"),
           contexto_obrigatorio=True, janela=80, nome="saude:cid-sem-rotulo"),
    # Código da CID precedido de "código" ("doença de Huntington, código G10"), sem decimal.
    Padrao("SAUDE", r"(?<=\bc[óo]digo\s{1,3})(?-i:[A-TV-Z]\d{2}(?:\.\d{1,2})?)\b", 0.6, camada=SEMANTICA,
           contexto=("cid", "diagn[óo]stico", "laudo", "doen[çc]a", "s[íi]ndrome", "transtorno", "patologia"),
           contexto_obrigatorio=True, janela=80, nome="saude:cid-codigo"),
]
#: Qualificadores incluídos no trecho tarjado, pois também revelam a condição: gravidade ou estágio
#: ("asma grave", "câncer em estágio avançado"), tipo ou mecanismo ("carcinoma basocelular",
#: "dermatite de contato", "depressão pós-parto"), especialidade ("cirurgia cardíaca pediátrica") e
#: localização anatômica ("tuberculose pulmonar", "artrose no quadril", "câncer de próstata"). Até três
#: em sequência ("hipertensão arterial sistêmica severa").
_GRAVIDADE = (r"sever[oa]s?|graves?|leves?|moderad[oa]s?|cr[ôo]nic[oa]s?|agud[oa]s?|avan[çc]ad[oa]|inicial|"
              r"constantes?|intens[oa]s?|frequentes?|"
              r"terminal|maligna|maligno|benign[oa]|descompensad[oa]|persistente|refrat[áa]ri[oa]|"
              r"profund[oa]|bilateral|cong[êe]nit[oa]|heredit[áa]ri[oa]|remitente(?:[- ]recorrente)?|recorrente|"
              r"(?:em\s+)?est[áa]gio\s+\w+|tipo\s+[12]|de\s+grau\s+\w+")
_TIPO_CLINICO = (r"pulmonar(?:es)?|renal|renais|card[íi]ac[oa]s?|hep[áa]tic[oa]s?|lombar(?:es)?|cervica(?:l|is)|tor[áa]cic[oa]|"
                 r"intestina(?:l|is)|g[áa]stric[oa]|cerebra(?:l|is)|ocular(?:es)?|[óo]sse[oa]s?|muscular(?:es)?|cut[âa]ne[oa]|"
                 r"sist[êe]mic[oa]|perif[ée]ric[oa]|arterial|venos[oa]|basocelular|espinocelular|ductal|lobular|"
                 r"invasiv[oa]|metast[áa]tic[oa]|bacterian[oa]|viral|f[úu]ngic[oa]|al[ée]rgic[oa]|infantil|juvenil|"
                 r"gestacional|p[óo]s-parto|puerperal|adquirid[oa]|resistente|multirresistente|extrus[oa]|protrus[oa]|"
                 r"respirat[óo]ri[oa]s?|p[óo]s-operat[óo]ri[oa]s?|neonatal|"
                 r"eritematos[oa]|ulcerativ[oa]|obstrutiv[oa]|hipertr[óo]fic[oa]|dilatad[oa]|isqu[êe]mic[oa]|"
                 r"hemorr[áa]gic[oa]|idiop[áa]tic[oa]|degenerativ[oa]|espástic[oa]|diab[ée]tic[oa]|proliferativ[oa]|"
                 r"linfoide|mieloide|linfoc[íi]tic[oa]|prost[áa]tic[oa]|mam[áa]ri[oa]|uterin[oa]|coronarian[oa]|"
                 r"dent[áa]ri[oa]s?|auditiv[oa]|pedi[áa]tric[oa]|geri[áa]tric[oa]|oftalmol[óo]gic[oa]|ortop[ée]dic[oa]|"
                 r"neurol[óo]gic[oa]|bari[áa]tric[oa]|vascular|eletiv[oa]s?|pl[áa]stic[oa]|oncol[óo]gic[oa]|urol[óo]gic[oa]|"
                 r"ginecol[óo]gic[oa]|reparador[a]|abdomina(?:l|is)|in\s+situ|de\s+contato|com\s+espasticidade|"
                 r"de\s+[âa]ngulo\s+(?:aberto|fechado)")
_PARTE_DO_CORPO = (r"pr[óo]stata|mamas?|seios?|pulm[ãa]o|pulm[õo]es|f[íi]gado|rins?|[úu]tero|colo\s+do\s+[úu]tero|ov[áa]rios?|"
                   r"pele|c[óo]lon|intestino|est[ôo]mago|p[âa]ncreas|tireoide|c[ée]rebro|coluna(?:\s+(?:lombar|cervical|"
                   r"vertebral))?|quadril|joelhos?|ombros?|f[êe]mur|t[íi]bia|pernas?|bra[çc]os?|p[ée]s?|m[ãa]os?|punhos?|"
                   r"tornozelos?|olhos?|retina|c[óo]rnea|cora[çc][ãa]o|bexiga|ves[íi]cula(?:\s+biliar)?|boca|garganta|"
                   r"laringe|es[ôo]fago|reto|ossos?|medula(?:\s+[óo]ssea)?|cabe[çc]a|cotovelos?|mand[íi]bula|ouvidos?|"
                   r"pesco[çc]o|test[íi]culos?|cr[âa]nio|dedos?")
_QUALIFICADOR = (r"(?:\s+(?:" + _GRAVIDADE + "|" + _TIPO_CLINICO + r"|(?:d[eoa]s?|n[oa]s?|em)\s+(?:" + _PARTE_DO_CORPO
                 + r")))")
#: Sigla entre parênteses logo após o nome ("esclerose lateral amiotrófica (ELA)").
_SIGLA = r"(?:\s*\((?-i:[A-Z][A-Z0-9]{1,6}(?:[/-][A-Z0-9]{1,6})?)\))?"
_DOENCA = r"(?:" + "|".join(DOENCAS) + r")" + _QUALIFICADOR + r"{0,3}" + _SIGLA
#: Sal ou éster antes do nome do fármaco ("cloridrato de metformina", "carbonato de lítio").
_SAL = (r"(?:(?:cloridrato|dicloridrato|sulfato|maleato|besilato|fumarato|hemifumarato|succinato|tartarato|citrato|"
        r"acetato|fosfato|carbonato|valerato|propionato|dipropionato|mesilato|bromidrato|oxalato|pamoato|decanoato|"
        r"furoato)\s+de\s+)?")
#: Classes terapêuticas pelo sufixo da DCB: anticorpos monoclonais (-mabe), proteínas de fusão
#: (-cepte), inibidores de quinase (-tinibe), gliflozinas, gliptinas, sartanas, estatinas, inibidores da
#: bomba de prótons (-prazol), benzodiazepínicos (-azepam) e antidepressivos (-xetina).
_SUFIXO_FARMACO = (r"[a-záéíóúâêôãõç]{3,}(?:mabe|cepte|tinibe|gliflozina|gliptina|sartana|statina|prazol|azepam|"
                   r"xetina)")
#: Sal ou forma após o nome ("losartana potássica", "dipirona sódica").
_FORMA = r"(?:\s+(?:pot[áa]ssic[oa]|s[óo]dic[oa]|c[áa]lcic[oa]|magn[ée]sic[oa]|monoidratad[oa]|di-?hidratad[oa]))?"
#: Dose após o nome ("500mg", "40 mg/dia", "10 UI").
_DOSE = r"(?:\s*\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|g|ml|ui)(?:\s*/\s*(?:ml|dose|dia|kg))?)?"
_MEDICAMENTO = _SAL + r"(?:" + _medicamentos() + "|" + _SUFIXO_FARMACO + r")" + _FORMA + _DOSE
#: Objetos que fazem de "tratamento de…" um termo administrativo, não de saúde ("tratamento de dados
#: pessoais", "tratamento de esgoto", "tratamento isonômico").
_TRATAMENTO_NAO_SAUDE = (r"(?!(?:isonômico|isonomico|igualit[áa]rio|diferenciado|desigual|tribut[áa]rio|fiscal|"
                         r"preferencial|dispensado)\b)")
_OBJETO_NAO_SAUDE = (r"(?!(?:os\s+|as\s+|o\s+|a\s+)?(?:dados|informa[çc](?:[ãa]o|[õo]es)|esgotos?|[áa]guas?|res[íi]duos|"
                     r"efluentes|lixo|documentos|processos|reclama[çc][õo]es|den[úu]ncias|demandas|pedidos|recursos|"
                     r"mensagens|manifesta[çc][õo]es|ocorr[êe]ncias|quest[õo]es|casos\s+omissos)\b)")
#: Regras de saúde baseadas em termos isolados. Os casamentos podem se sobrepor: em "cirurgia de câncer
#: de próstata", "cirurgia de câncer" não impede o reconhecimento de "câncer de próstata".
SAUDE_SEMANTICA = [
    Padrao("SAUDE", r"\b" + _DOENCA + r"(?!\w)", 0.8, camada=SEMANTICA, nome="saude:termo", sobrepostos=True),
    # Medicamento citado sem verbo de uso: "a falta de insulina glargina na rede" é de interesse
    # público; "minha filha precisa de insulina glargina" é dado de saúde (ver camada semântica).
    Padrao("SAUDE", r"\b" + _MEDICAMENTO + r"\b", 0.8, camada=SEMANTICA, nome="saude:medicamento"),
    Padrao("SAUDE", r"\btratamentos?\s+" + _TRATAMENTO_NAO_SAUDE + r"(?:\w+\s+)?(?:de|para|contra|da|do)\s+"
           + _OBJETO_NAO_SAUDE + r"[^\n.;,()]{3,50}", 0.75, camada=SEMANTICA, nome="saude:tratamento-de"),
]
# Termo de saúde precedido de verbo ou expressão que o atribui a alguém ("possui diabetes", "convive com
# HIV", "minha filha está com suspeita de dengue", "sofri uma fratura"): deixa de ser termo isolado e
# passa à camada contextual. Apenas o termo é tarjado, não o verbo. Formas do plural ("possuem",
# "têm") ficam de fora, pois descrevem grupos, assim como "trata", que costuma ter instituição como
# sujeito ("o hospital trata câncer").
_ATRIBUICAO = (r"possui|possuo|apresenta|apresento|apresentou|apresentava|teve|tive|tinha|tenho|desenvolveu|desenvolvi|"
               r"contraiu|contra[íi]|peguei|pegou|sofreu|sofri|trato|tratei|convive\s+com|convivo\s+com|"
               r"portador(?:a)?\s+de|tem|"
               r"(?:est(?:ou|á|a|ava|ive|eve)|t[áa]|t[ôo]|fiquei|ficou|internad[oa])\s+com|"
               r"(?:luto|luta|lutou)\s+contra|venho\s+sofrendo\s+(?:de|com)|faleceu\s+(?:de|por)")
_COMPLEMENTO = (r"(?:\s+(?:um|uma|o|a))?(?:\s+(?:quadro|diagn[óo]stico|suspeita|hist[óo]rico|caso|crise|crises)"
                r"(?:\s+(?:cl[íi]nico|grave|severo|preliminar|confirmado))?\s+de)?")
SAUDE_CONTEXTUAL.append(
    Padrao("SAUDE", r"\b(?:" + _ATRIBUICAO + r")" + _COMPLEMENTO + r"\s{1,3}(" + _DOENCA + r")(?!\w)", 0.9,
           camada=CONTEXTUAL, grupo=1, nome="saude:possui", sobrepostos=True))
# Registro clínico de um caso ("prontuário referente à intoxicação…", "laudo de autismo", "quadro de
# malária grave") e campo de formulário ("Condição clínica: paralisia cerebral"): referem-se a uma
# pessoa determinada mesmo sem pronome na frase.
SAUDE_CONTEXTUAL.append(
    Padrao("SAUDE", r"\b(?:(?:laudos?|atestados?|prontu[áa]rios?)(?:\s+(?:m[ée]dicos?|cl[íi]nicos?))?\s+"
                    r"(?:de|sobre|referentes?\s+(?:a|à|ao)|que\s+(?:atesta|comprova|indica))(?:\s+(?:o|a|um|uma))?|"
                    r"quadro\s+(?:cl[íi]nico\s+)?(?:grave\s+)?de|crise\s+de|"
                    r"(?:condi[çc][ãa]o\s+cl[íi]nica|quadro\s+cl[íi]nico|diagn[óo]stico|hip[óo]tese\s+diagn[óo]stica|"
                    r"patologia|doen[çc]a|comorbidades?|enfermidade)\s*:)\s{0,3}(" + _DOENCA + r")(?!\w)", 0.9,
           camada=CONTEXTUAL, grupo=1, nome="saude:registro-clinico", sobrepostos=True))
# Medicamento precedido de verbo de uso ou prescrição ("tomo fluoxetina", "faz uso de insulina NPH").
SAUDE_CONTEXTUAL.append(
    Padrao("SAUDE", r"(?<=\b(?:tomo|toma|tomam|tomando|tomava|fa[çz]o\s+uso\s+de|faz\s+uso\s+de|fazendo\s+uso\s+de|"
                    r"uso\s+cont[íi]nuo\s+de|receitou|prescreveu|prescrit[oa]s?|receitad[oa]s?)\s{1,3}(?:[oa]\s+)?)"
           + _MEDICAMENTO + r"\b", 0.9, camada=CONTEXTUAL, nome="saude:uso-medicamento"))

# --------------------------------------------------------------------------- Outros sensíveis
#: Termos das demais categorias de dado sensível do art. 5º, II, da LGPD.
SENSIVEIS_SEMANTICA = [
    Padrao("RELIGIAO", _termos(
        r"cat[óo]lic[oa]s?(?:\s+praticante)?", r"evang[ée]lic[oa]s?", r"esp[íi]rita", r"umbandista", r"umbanda",
        r"candombl[ée]", r"candomblecista", r"judeu|judia|judaica?", r"mu[çc]ulman[oa]s?", r"isl[âa]mic[oa]",
        r"budista", r"hindu[íi]sta", r"ateu|ateia", r"agn[óo]stic[oa]", r"testemunhas?\s+de\s+jeov[áa]",
        r"adventista", r"pentecostal", r"presbiterian[oa]", r"batista", r"m[óo]rmon", r"protestante",
        r"minha\s+(?:religi[ãa]o|f[ée]|cren[çc]a)", r"pr[áa]tica\s+religiosa", r"pai\s+de\s+santo", r"m[ãa]e\s+de\s+santo",
        r"convic[çc][ãa]o\s+religiosa", r"religi[ãa]o\s+de\s+matriz\s+africana"), 0.8, camada=SEMANTICA),
    Padrao("OPINIAO_POLITICA", _termos(
        r"filiad[oa]\s+(?:ao|à)\s+(?:partido\s+)?[A-Z][\w-]+", r"militante\s+(?:do|da|de)\s+\w+", r"bolsonarista",
        r"lulista", r"petista", r"tucan[oa]", r"comunista", r"socialista", r"anarquista", r"eleitor(?:a)?\s+(?:do|da|de)\s+\w+",
        r"vot(?:ei|ou|amos|aram)\s+(?:em|no|na)\s+\w+", r"meu\s+voto", r"simpatizante\s+(?:do|da|de)\s+\w+",
        r"opini[ãa]o\s+pol[íi]tica", r"persegui[çc][ãa]o\s+pol[íi]tica", r"posicionamento\s+pol[íi]tico",
        r"sou\s+(?:militante|ativista|filiad[oa]|simpatizante|conservador(?:a)?|progressista|de\s+esquerda|"
        r"de\s+direita|comunista|socialista|anarquista|liberal)", r"minha\s+ideologia",
        r"particip(?:o|ei|amos|ava)\s+d[aoe]s?\s+(?:greve|manifesta[çc][ãa]o|protesto|movimentos?\s+socia(?:l|is)|ato)\w*",
        r"fui\s+candidat[oa](?:\s+a\s+\w+)?", r"membro\s+d[aoe]\s+partido(?:\s+\w+)?"),
        0.8, camada=SEMANTICA),
    Padrao("FILIACAO_SINDICAL", _termos(
        r"sindicalizad[oa]", r"sindicalista", r"filiad[oa]\s+(?:ao|à)\s+sindicato(?:\s+\w+)?",
        r"membro\s+do\s+sindicato(?:\s+\w+)?", r"associad[oa]\s+(?:ao|à)\s+sindicato(?:\s+\w+)?",
        r"dirigente\s+sindical", r"representante\s+sindical", r"delegad[oa]\s+sindical", r"ma[çc]om",
        r"ma[çc]onaria", r"filia[çc][ãa]o\s+sindical", r"membro\s+d[ao]\s+(?:CUT|CTB|UGT|CSP-Conlutas|For[çc]a\s+Sindical)",
        r"diretor(?:a)?\s+do\s+sindicato(?:\s+\w+)?", r"sou\s+sindicalizad[oa]",
        r"sou\s+membro\s+d[aoe]\s+(?:associa[çc][ãa]o|cooperativa|movimento|sindicato)(?:\s+\w+)*?(?=[.,;]|$)"),
        0.85, camada=SEMANTICA),
    Padrao("VIDA_SEXUAL", _termos(
        r"homossexual", r"heterossexual", r"bissexual", r"pansexual", r"assexual", r"gay", r"l[ée]sbica",
        r"transexual", r"transg[êe]ner[oa]", r"travesti", r"pessoas?\s+trans", r"mulher(?:es)?\s+trans",
        r"home(?:m|ns)\s+trans", r"trans", r"processo\s+transexualizador", r"hormoniza[çc][ãa]o", r"terapia\s+hormonal",
        r"n[ãa]o[- ]bin[áa]ri[oa]", r"intersexo", r"lgbt\w*\+?", r"orienta[çc][ãa]o\s+sexual", r"identidade\s+de\s+g[êe]nero",
        r"nome\s+social", r"vida\s+sexual", r"rela[çc][ãa]o\s+homoafetiva", r"homoafetiv[oa]", r"companheir[oa]\s+do\s+mesmo\s+sexo"),
        0.85, camada=SEMANTICA),
    Padrao("GENETICO_BIOMETRICO", _termos(
        r"exame\s+de\s+dna", r"teste\s+(?:de\s+)?(?:dna|gen[ée]tico)", r"perfil\s+gen[ée]tico", r"doen[çc]a\s+gen[ée]tica",
        r"mapeamento\s+gen[ée]tico", r"dados?\s+biom[ée]tricos?", r"biometria(?:\s+facial)?", r"impress[ãa]o\s+digital",
        r"impress[õo]es\s+digitais", r"reconhecimento\s+facial", r"leitura\s+de\s+[íi]ris", r"dados?\s+gen[ée]ticos?"),
        0.85, camada=SEMANTICA),
    Padrao("ORIGEM_RACIAL", _termos(
        r"negr[oa]s?", r"pret[oa]s?", r"pard[oa]s?", r"ind[íi]gena", r"quilombola", r"afrodescendentes?",
        r"afro-?brasileir[oa]s?", r"autodeclarad[oa]\s+\w+", r"cor\s+da\s+pele", r"origem\s+(?:[ée]tnica|racial)",
        r"etnia\s+\w+", r"ra[çc]a\s+\w+", r"cotista\s+racial", r"racismo", r"inj[úu]ria\s+racial",
        r"comunidade\s+(?:quilombola|ind[íi]gena|cigana)"), 0.75, camada=SEMANTICA),
]

# --------------------------------------------------------------------------- Intimidade e risco (LAI art. 31)
#: Relatos de violência e de situação de risco. A divulgação pode expor a vítima a nova violência;
#: por isso a confiança é alta e a camada é contextual.
INTIMIDADE_CONTEXTUAL = [
    # Tipos de violência, com o enquadramento opcional ("vítima de", "medo de").
    Padrao("VIOLENCIA",
           r"\b(?:(?:medo|v[íi]tima|situa[çc][ãa]o|sofr(?:e|o|i|endo|eu)|alvo)\s+de\s+)?(?:viol[êe]ncia\s+"
           r"(?:dom[ée]stica|familiar|sexual|f[íi]sica|psicol[óo]gica|patrimonial|obst[ée]trica|contra\s+a\s+mulher)|"
           r"abuso\s+(?:sexual|f[íi]sico|psicol[óo]gico)|estupro(?:\s+de\s+vulner[áa]vel)?|ass[ée]dio\s+(?:moral|sexual)|"
           r"medida\s+protetiva(?:\s+de\s+urg[êe]ncia)?|"
           r"amea[çc]as?\s+de\s+morte|c[áa]rcere\s+privado|tentativa\s+de\s+(?:homic[íi]dio|feminic[íi]dio|suic[íi]dio)|"
           r"feminic[íi]dio|explora[çc][ãa]o\s+sexual|tr[áa]fico\s+de\s+pessoas|inj[úu]ria\s+racial)",
           0.95, camada=CONTEXTUAL, nome="intimidade:violencia"),
    # Relatos em primeira pessoa de ameaça, agressão, fuga ou risco à vida.
    Padrao("VIOLENCIA",
           r"\b(?:estou\s+em\s+perigo|corro\s+risco|fugindo\s+de\s+casa|preciso\s+de\s+abrigo|casa[- ]abrigo|"
           r"escolta\s+policial|medo\s+de\s+denunciar|n[ãa]o\s+tenho\s+para\s+onde\s+ir|vai\s+me\s+matar|"
           r"amea[çc]ou\s+me\s+matar|me\s+amea[çc](?:a|ou|ando)|me\s+persegue|me\s+agrid(?:e|iu)|me\s+bate|me\s+bateu|"
           r"me\s+espanc\w+|me\s+humilh\w+|marcas\s+no\s+corpo|quebrou\s+a\s+medida|agredid[oa]\s+(?:pel[oa]|por)\s+\w+|"
           r"sofr(?:o|i)\s+(?:agress[õo]es|amea[çc]as|viol[êe]ncia)|recebi\s+amea[çc]as|tentou\s+me\s+\w+|"
           r"medo\s+de\s+(?:sofrer\s+)?(?:viol[êe]ncia|apanhar|agress[ãa]o|morrer|ser\s+morta?)|"
           r"situa[çc][ãa]o\s+de\s+(?:risco|viol[êe]ncia|vulnerabilidade)|me\s+vigia|controla\s+tudo|"
           r"fugi\s+de\s+casa|amea[çc]a\s+levar\s+(?:meus|minhas|os|as)\s+filh[oa]s|apanh(?:ar|ei|o)\s+(?:de|do|da|novamente)|"
           r"tentativa\s+de\s+suic[íi]dio|pensamentos\s+suicidas|idea[çc][ãa]o\s+suicida|automutila[çc][ãa]o)",
           0.95, camada=CONTEXTUAL, nome="intimidade:risco"),
]
#: Termos isolados de vida privada: violência, conflitos familiares, situação prisional.
INTIMIDADE_SEMANTICA = [
    Padrao("VIOLENCIA", _termos(r"agress[ãa]o", r"agress[õo]es", r"viol[êe]ncia", r"medo\s+de\s+retalia[çc][ãa]o",
                                r"agredid[oa]", r"amea[çc]ad[oa]", r"espancad[oa]", r"abusad[oa]",
                                r"violentad[oa]", r"suic[íi]dio", r"trai[çc][ãa]o", r"div[óo]rcio", r"separa[çc][ãa]o\s+"
                                r"(?:conjugal|judicial)", r"pens[ãa]o\s+aliment[íi]cia", r"guarda\s+(?:dos?\s+filhos?|"
                                r"compartilhada|unilateral)", r"usu[áa]ri[oa]\s+de\s+drogas", r"presidi[áa]ri[oa]",
                                r"egress[oa]\s+do\s+sistema\s+prisional", r"antecedentes\s+criminais", r"condenad[oa]"),
            0.75, camada=SEMANTICA, nome="intimidade:termo"),
]

# --------------------------------------------------------------------------- Menores (LGPD art. 14)
#: Referências a criança ou adolescente determinado e a situações protegidas pelo ECA.
MENOR_CONTEXTUAL = [
    # Criança ou adolescente com a idade ("meu filho de 8 anos"): a idade, combinada ao vínculo
    # familiar do requerente, identifica o menor.
    Padrao("DADO_DE_MENOR",
           r"\b(?:(?:minhas?|meus?|suas?|seus?|as?|os?)\s+)?(?:crian[çc]as?|beb[êe]s?|adolescentes?|filh[oa]s?|net[oa]s?|"
           r"entead[oa]s?|menin[oa]s?|menor(?:es)?|dependentes?)\s+(?:de|com)\s+\d{1,2}\s+(?:anos?|meses)"
           r"(?:\s+de\s+idade)?", 0.9, camada=CONTEXTUAL, nome="menor:idade"),
    # Medidas e procedimentos do ECA cuja divulgação é vedada (arts. 17 e 143).
    Padrao("DADO_DE_MENOR",
           r"\b(?:conselho\s+tutelar|medida\s+socioeducativa|ato\s+infracional|acolhimento\s+institucional|"
           r"abrigo\s+de\s+menores|guarda\s+provis[óo]ria|destitui[çc][ãa]o\s+do\s+poder\s+familiar|"
           r"processo\s+de\s+ado[çc][ãa]o|menor\s+infrator(?:a)?|menor\s+sob\s+guarda|menor\s+de\s+idade\s+sob\s+\w+\s+"
           r"(?:responsabilidade|guarda|tutela)|menor\s+[óo]rf[ãa]o?|sob\s+tutela(?:\s+do\s+estado)?|"
           r"crian[çc]a\s+em\s+situa[çc][ãa]o\s+de\s+(?:abrigo|rua|risco|acolhimento))", 0.85, camada=CONTEXTUAL,
           nome="menor:situacao"),
]

# --------------------------------------------------------------------------- Quase-identificadores
# Descrições que, sem nome, apontam para uma pessoa determinada: a função somada ao posto, ao turno, à
# data ou à circunstância em que a pessoa foi encontrada ("a atendente do guichê 3 no plantão da manhã",
# "o fiscal que esteve aqui no dia 12/05 às 10h"). Basta uma dessas descrições para que o órgão, ou
# qualquer colega, saiba de quem se trata; por isso são sinalizadas para revisão (perfil LAI) ou
# tarjadas (perfis de ouvidoria e de educação).
#
# A descrição tem três partes: a palavra que a introduz (artigo, contração ou "como", "sou", "era"),
# que distingue a função de usos adjetivos ("nota fiscal", "parecer técnico"); a função; e a cadeia de
# complementos que a delimitam — locuções preposicionadas ("do guichê 4", "no turno da manhã"), orações
# relativas ("que me atendeu") e advérbios de tempo e lugar ("ontem", "aqui"). Só é sinalizada a
# descrição cuja cadeia contém um elemento que individualiza a pessoa (ver :data:`_INDIVIDUALIZA`):
# "o servidor do setor de protocolo", sozinho, designa qualquer servidor do setor.

#: Funções e ocupações de quem atende o público ou presta serviço, no singular. O feminino fica de fora
#: quando coincide com objeto ou conceito comum ("a carteira", "a porteira", "a mecânica").
_FUNCOES = (
    # Atendimento, portaria e segurança
    r"atendente", r"recepcionista", r"telefonista", r"balconista", r"bilheteir[oa]", r"porteiro", r"vigilante",
    r"vigia", r"sentinela", r"zelador(?:a)?", r"bombeir[oa]", r"brigadista", r"salva-vidas", r"guarda-vidas",
    r"gar[çc]om", r"gar[çc]onete", r"ajudante", r"servente", r"coletor(?:a)?",
    # Transporte
    r"motorista", r"cobrador(?:a)?", r"condutor(?:a)?", r"maquinista", r"operador", r"carteiro",
    r"entregador(?:a)?", r"frentista", r"manobrista", r"despachante", r"comiss[áa]ri[oa]\s+de\s+bordo",
    r"controlador(?:a)?\s+de\s+(?:tr[áa]fego|voo|acesso)",
    # Serviço público, fiscalização e polícia
    r"servidor(?:a)?", r"funcion[áa]ri[oa]", r"colaborador(?:a)?", r"terceirizad[oa]", r"estagi[áa]ri[oa]",
    r"bolsista", r"aprendiz", r"volunt[áa]ri[oa]", r"fiscal", r"inspetor(?:a)?", r"auditor(?:a)?", r"perit[oa]",
    r"vistoriador(?:a)?", r"avaliador(?:a)?", r"examinador(?:a)?", r"aplicador(?:a)?", r"pregoeir[oa]",
    r"escriv[ãa]o?", r"conferente", r"almoxarife", r"agente", r"policial", r"oficial\s+de\s+justi[çc]a",
    r"carcereir[oa]", r"investigador(?:a)?", r"escrevente", r"recenseador(?:a)?", r"entrevistador(?:a)?",
    r"conciliador(?:a)?", r"mediador(?:a)?",
    # Chefia
    r"supervisor(?:a)?", r"gerente", r"chefe", r"encarregad[oa]", r"coordenador(?:a)?", r"vice-diretor(?:a)?",
    r"diretor(?:a)?", r"gestor(?:a)?",
    # Educação, cultura e esporte
    r"professor(?:a)?", r"docente", r"tutor(?:a)?", r"monitor(?:a)?", r"instrutor(?:a)?", r"treinador(?:a)?",
    r"educador(?:a)?", r"orientador(?:a)?", r"pedagog[oa]", r"bibliotec[áa]ri[oa]", r"merendeir[oa]",
    r"int[ée]rprete", r"cuidador(?:a)?", r"palestrante", r"oficineir[oa]", r"preceptor(?:a)?",
    # Saúde
    r"m[ée]dic[oa]", r"enfermeir[oa]", r"t[ée]cnic[oa]", r"auxiliar", r"assistente", r"dentista",
    r"odont[óo]log[oa]", r"nutricionista", r"farmac[êe]utic[oa]", r"fisioterapeuta", r"fonoaudi[óo]log[oa]",
    r"psic[óo]log[oa]", r"psiquiatra", r"terapeuta", r"pediatra", r"ortopedista", r"ginecologista", r"obstetra",
    r"cardiologista", r"neurologista", r"anestesista", r"cirurgi(?:[ãa]o|ã)", r"cl[íi]nic[oa]\s+geral", r"plantonista",
    r"socorrista", r"param[ée]dic[oa]", r"maqueir[oa]", r"veterin[áa]ri[oa]", r"biom[ée]dic[oa]", r"radiologista",
    r"vacinador(?:a)?",
    # Técnicos, obras e manutenção
    r"analista", r"engenheir[oa]", r"arquitet[oa]", r"agr[ôo]nom[oa]", r"agrimensor(?:a)?", r"top[óo]graf[oa]",
    r"ge[óo]log[oa]", r"extensionista", r"pesquisador(?:a)?", r"arquivista", r"consultor(?:a)?", r"mec[âa]nico",
    r"eletricista", r"encanador(?:a)?", r"pedreir[oa]", r"mestre\s+de\s+obras", r"oper[áa]ri[oa]", r"gari",
    r"varredor(?:a)?", r"faxineir[oa]", r"cozinheir[oa]", r"copeir[oa]", r"jardineir[oa]",
    # Referência coloquial a quem atendeu
    r"rapaz", r"mo[çc][oa]",
)
#: Palavra que introduz a função como pessoa: artigo, contração, demonstrativo, possessivo, "como",
#: verbos de ligação ("sou motorista", "trabalhei como vigilante"), "na função de" e "na qualidade de"
#: ou rótulo ("Servidor envolvido:").
_INTRODUZ = (r"(?<=(?:(?:^|[^\w])(?:o|a|um|uma|do|da|no|na|pelo|pela|ao|à|num|numa|dum|duma|"
             r"(?:d|n|daqu|naqu|aqu)?(?:est|ess|el)[ea]|aquel[ea]|como|sou|era|fui|é|foi|seu|sua|meu|minha|nosso|"
             r"nossa|pr[oa]s?|prum|pruma|(?:fun[çc][ãa]o|qualidade|condi[çc][ãa]o)\s+de)\s+)|:\s*)")
#: "Segurança" e "guarda municipal" só designam a pessoa no masculino ("o segurança", "o guarda
#: municipal"); no feminino, são o conceito ("a segurança do paciente") e a corporação.
_INTRODUZ_MASC = r"(?<=(?:^|[^\w])(?:o|um|do|no|pelo|ao|num|dum|(?:d|n|daqu|naqu|aqu)?(?:est|ess|el)e|como|sou|era|fui)\s+)"
_PREPOSICAO = (r"(?:d[oa]s?|de|n[oa]s?|em|num|numa|pel[oa]s?|ao|aos|à|às|a|as|entre|durante|desde|at[ée]|sobre|"
               r"sentido|com|como|d(?:aquel|est|ess)[ea]s?|n(?:aquel|est|ess)[ea]s?)")
#: Palavras que encerram a descrição: conjunções, pronomes, artigos, verbos de ligação e advérbios que
#: costumam iniciar a oração principal ("o atendente do guichê 4 *me* disse…").
_PARADA = (r"(?:que|quem|qual|quais|cuj[oa]s?|e|ou|nem|mas|pois|porque|por[ée]m|quando|onde|enquanto|se|n[ãa]o|"
           r"me|nos|lhe|lhes|te|mim|ele|ela|eles|elas|eu|voc[êe]s?|o|os|um|uma|uns|umas|[ée]|foi|era|eram|s[ãa]o|"
           r"est[áa]|estava|estavam|esteve|tem|t[êe]m|tinha|teve|h[áa]|havia|pode|podia|deve|deveria|precisa|disse|"
           r"diz|fala|sabe|quer|vai|ia|fica|faz|fez|deu|d[áa]|sempre|nunca|tamb[ée]m|ainda|j[áa]|muito|mais|menos|"
           r"quase|s[óo]|apenas|ent[ãa]o|para|pra|pro|por|sem|sob|conforme|contra|perante|ap[óo]s|aqui|l[áa]|ali|"
           r"ontem|anteontem|hoje|cedo|(?-i:[a-zà-ú]+r(?:á|ão)))")
_PALAVRA = r"(?:(?:av|r|rod|qd|cj|conj|lt|dr|dra|sr|sra|prof|profa)\.|\w+(?:[-'’./:]\w+)*)"
_NUCLEO = rf"(?!(?:{_PARADA}|{_PREPOSICAO})\b){_PALAVRA}"
#: Modificador do núcleo; não pode ter terminação típica de verbo flexionado ou no infinitivo
#: ("recebeu", "barrou", "cumprir").
_MODIFICADOR = (rf"(?!(?:{_PARADA}|{_PREPOSICAO})\b)(?!\w+(?:ou|eu|iu|ava|avam|aram|eram|iram|ndo|er|ir)\b)"
                rf"{_PALAVRA}")
#: Número com a indicação que o acompanha: "4", "3º ano C", "204 Sul", "12/05/2024", "10h30".
_NUMERO = (r"\d\w*(?:[./:\-]\w+)*(?:\s+(?:ano|s[ée]rie|semestre|andar|horas?))?"
           r"(?:\s+(?-i:[A-Z])\b|\s+(?:sul|norte|leste|oeste)\b)?")
_DETERMINANTE = r"(?:o|a|os|as|um|uma|minha|meu|minhas|meus|nossa|nosso|sua|seu|ess[ea]s?|est[ea]s?|aquel[ea]s?)"
_SINTAGMA = (rf"(?:{_DETERMINANTE}\s+)?(?:{_NUMERO}|{_NUCLEO}(?:\s+{_MODIFICADOR}){{0,4}}"
             rf"(?:\s+{_NUMERO}|\s+(?-i:[A-Z])\b)?)")
#: Primeira palavra da oração relativa, que deve ser o verbo: não pode ser artigo, pronome ou conjunção.
_NAO_VERBO = (r"(?:o|a|os|as|um|uma|ele|ela|eles|elas|eu|voc[êe]s?|n[ãa]o|que|e|ou|se|me|nos|lhe|"
              r"meus?|minhas?|seus?|suas?|nossos?|nossas?|est[ea]s?|ess[ea]s?|d[oa]s?|de|n[oa]s?|em|para|pra|por|com)")
_DIA_SEMANA = r"(?:(?:segunda|ter[çc]a|quarta|quinta|sexta)s?(?:[- ]feiras?)?|s[áa]bados?|domingos?)"
_MES = r"(?:janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
#: Elementos da cadeia de complementos.
_COMPLEMENTO = (
    rf"(?:(?:at[ée]\s+)?{_PREPOSICAO}|por\s+volta\s+d(?:e|[ao]s?)|em\s+frente\s+(?:a[os]?|à)|ao\s+lado\s+d[eoa]s?|"
    rf"perto\s+d[eoa]s?|pr[óo]xim[oa]\s+(?:a[os]?|à)|referente\s+(?:a[os]?|à)|l[áa]\s+n[oa]s?)\s+{_SINTAGMA}",
    # Oração relativa: "que me atendeu", "que esteve aqui", "que realizou a vistoria".
    rf"que\s+(?:(?:me|nos|lhe|se|te)\s+)?(?!{_NAO_VERBO}\b){_PALAVRA}(?:\s+(?:aqui|l[áa]|ali|ontem|hoje|cedo))?"
    rf"(?:\s+\w+(?:ad|id)[oa]s?\b|\s+{_DETERMINANTE}\s+{_NUCLEO}(?:\s+{_MODIFICADOR}){{0,2}}|\s+{_MODIFICADOR})?",
    r"(?:d[ea]\s+)?(?:ontem|anteontem|hoje)|aqui|l[áa]|ali|cedo",
    r"(?:(?:n[oa]\s+)?(?:[úu]ltim[oa]\s+)?(?:semana|m[êe]s|ano|semestre)\s+passad[oa]|"
    r"(?:d|n)(?:est|ess)[ea]\s+(?:semana|m[êe]s|ano|semestre))",
    r"dia\s+\d{1,2}(?:/\d{1,2}(?:/\d{2,4})?)?",
    rf"e\s+(?:{_NUMERO}|{_DIA_SEMANA}|{_MES}|(?:jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\b)",
)
#: Vírgula seguida de novo complemento de tempo ou lugar: "ontem, dia 10, por volta das 15h".
_VIRGULA = (r"\s*,\s*(?=(?:n[oa]s?|num|numa|em|entre|durante|desde|at[ée]|sentido|por\s+volta|que|dia|ontem|"
            r"anteontem|hoje|l[áa])\b|(?:[àa]s?|d[ao]s|de)\s+\d)")
_CADEIA = r"(?:(?:" + _VIRGULA + r"|\s+)(?:" + "|".join(_COMPLEMENTO) + r")|\s*\([^()\n]{1,40}\))"
#: Elementos que individualizam a pessoa: turno, horário, data, dia da semana, posto de atendimento
#: identificado, oração relativa que narra o encontro ("que me atendeu", "que esteve aqui") ou a
#: indicação de responsável ("responsável pela vistoria"). "Período", "horário" e "semana", sozinhos,
#: não individualizam ("a carga horária no período letivo").
_INDIVIDUALIZA = re.compile(
    r"\b(?:turno|plant[ãa]o|escala|madrugada|manh[ãa]|tarde|noite|matutino|vespertino|noturno|diurno|temporada|"
    r"ontem|anteontem|hoje|(?:semana|m[êe]s|ano|semestre)\s+passad[oa]|[úu]ltim[oa]\s+(?:semana|m[êe]s|ano|semestre)|"
    r"(?:d|n)(?:est|ess)[ea]\s+(?:semana|m[êe]s|ano|semestre)|"
    rf"{_DIA_SEMANA}|fins?\s+de\s+semana|\d{{1,2}}\s+de\s+{_MES}|"
    r"guich[êe]|balc[ãa]o|guarita|port[ãa]o|cancela|cabine)\b"
    r"|\b\d{1,2}\s*(?:h\s*\d{0,2}|:\d{2}|\s+horas?)\b"
    r"|(?<![\d/])(?:0?[1-9]|[12]\d|3[01])/(?:0?[1-9]|1[0-2])(?:/(?:\d{4}|\d{2}))?\b(?!/)"
    r"|\bdia\s+\d{1,2}\b|\b(?:em|desde|de|entre)\s+(?:19|20)\d{2}\b"
    r"|\b(?:sala|bloco|mesa|caixa|posto|plataforma|ala|andar|linha|rota|viatura|ambul[âa]ncia|turma|s[ée]rie|ano|"
    r"laborat[óo]rio|galp[ãa]o|hangar|consult[óo]rio|pista|quadra|oficina|lote|terminal|box|baia|leito|"
    r"enfermaria|prefixo|setor|gleba|trecho|poste)\s+(?:n[º°o.]?\s*)?(?:\d+\w*|(?-i:[A-Z])\b)"
    r"|\bque\s+(?:me|nos|lhe)\s+\w+"
    r"|\bque\s+\w+(?:ou|eu|iu|ava|ia|eve|ez|eio)\b"
    r"|\bque\s+(?:atua|atende|trabalha|fica|faz|d[áa]|passa|circula|opera|coordena|leciona|cuida|acompanha|"
    r"conduz|presta)\b"
    r"|\brespons[áa]vel\s+pel[oa]s?\b|\bencarregad[oa]\s+d[eoa]s?\b|\bde\s+plant[ãa]o\b|\b[úu]nic[oa]\s",
    re.IGNORECASE)
_FUNCAO = (rf"(?:{_INTRODUZ}(?:ex-)?(?:(?:atual|[úu]nic[oa]|mesm[oa]|referid[oa])\s+)?(?:{'|'.join(_FUNCOES)})"
           rf"|{_INTRODUZ_MASC}(?:seguran[çc]a|guarda\s+(?:municipal|civil|patrimonial)))(?:-chefe)?\b")


#: Enunciado normativo, que trata da função em abstrato ("o servidor do plantão noturno deverá…",
#: "compete ao diretor da escola…"), e não de uma pessoa determinada.
_NORMATIVO_DEPOIS = re.compile(r"\s*,?\s*(?:dever[áã]o?|poder[áã]o?|caber[áã]o?|ter[áã]o?\s+(?:de|que)|"
                               r"fica(?:r[áã]o?)?\s+obrigad[oa]s?|est[áa]\s+obrigad[oa])\b", re.IGNORECASE)
_NORMATIVO_ANTES = re.compile(r"\b(?:cabe|caber[áa]|compete|competir[áa]|incumbe|incumbir[áa])\s+(?:ao?|à)\s+$",
                              re.IGNORECASE)


class _PadraoIndividualizado(Padrao):
    """:class:`Padrao` cujo achado só é aceito se contiver um elemento de :data:`_INDIVIDUALIZA` e não
    fizer parte de um enunciado normativo."""

    def detectar(self, texto: str) -> list:
        return [d for d in super().detectar(texto) if _INDIVIDUALIZA.search(texto[d.inicio:d.fim])
                and not _NORMATIVO_DEPOIS.match(texto, d.fim)
                and not _NORMATIVO_ANTES.search(texto[max(0, d.inicio - 20):d.inicio])]


QUASE_IDENTIFICADORES = [
    _PadraoIndividualizado("QUASE_IDENTIFICADOR", _FUNCAO + rf"(?:\s+{_MODIFICADOR}){{0,2}}(?:{_CADEIA}){{1,12}}",
                           0.6, camada=CONTEXTUAL, nome="quase:funcao-complemento"),
]


def reconhecedores():
    """Reconhecedores deste módulo, na forma esperada por :mod:`themis_lgpd.analisador`."""
    return [
        ReconhecedorPadroes("saude", SAUDE_CONTEXTUAL + SAUDE_SEMANTICA),
        ReconhecedorPadroes("sensiveis", SENSIVEIS_SEMANTICA),
        ReconhecedorPadroes("intimidade", INTIMIDADE_CONTEXTUAL + INTIMIDADE_SEMANTICA),
        ReconhecedorPadroes("menores", MENOR_CONTEXTUAL),
        ReconhecedorPadroes("quase_identificadores", QUASE_IDENTIFICADORES),
    ]
