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

from functools import cached_property
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
#: Numeral por extenso, nas quantidades que costumam acompanhar idade gestacional, duração e contagem.
_EXTENSO = (r"(?:um|uma|dois|duas|tr[êe]s|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|quatorze|catorze|quinze|"
            r"dezesseis|dezessete|dezoito|dezenove|vinte|trinta|quarenta)")
#: Substâncias psicoativas citadas em relatos de uso ("cheirava loló", "uso de pasta-base"). O álcool de
#: limpeza e o combustível não contam; "pedra" e "pó" só valem depois de verbo de uso ou de "usuário de".
_SUBSTANCIA = (r"(?:crack|coca[íi]na|pasta[- ]base(?:\s+de\s+coca[íi]na)?|maconha|haxixe|skunk|lol[óo]|lan[çc]a[- ]perfume|"
               r"cola\s+de\s+sapateiro|thinner|solventes?|"
               r"[áa]lcool(?!\s+(?:em\s+gel|gel|70|et[íi]lico\s+hidratado|isoprop[íi]lico|combust[íi]vel|anidro))|"
               r"bebidas?\s+alco[óo]licas?|cacha[çc]a|pinga|ecstasy|(?-i:LSD|MDMA)|hero[íi]na|metanfetamina|anfetaminas?|"
               r"rebites?|drogas(?:\s+il[íi]citas)?|subst[âa]ncias?\s+psicoativas?|entorpecentes)")
#: Serviço da rede de saúde mental e de álcool e drogas; o tratamento descrito pelo serviço ("segue no CAPS
#: AD", "duas internações em comunidade terapêutica") revela a condição.
_SERVICO_SAUDE_MENTAL = (r"(?:(?-i:CAPS)(?:\s*(?:(?-i:AD|ad|i|ij|IJ|II|III)\b|AD\s+III|infantojuvenil|infantil|[áa]lcool\s+e\s+drogas))*|"
                         r"(?-i:CAPSi|CAPSij)|Centro\s+de\s+Aten[çc][ãa]o\s+Psicossocial(?:\s+(?:[ÁA]lcool\s+e\s+Drogas|Infantojuvenil|"
                         r"Infantil|(?-i:AD|III|II|i)\b))*|ambulat[óo]rios?\s+de\s+(?:sa[úu]de\s+mental|psiquiatria|"
                         r"depend[êe]ncia\s+qu[íi]mica)|servi[çc]os?\s+(?:especializados?\s+)?de\s+sa[úu]de\s+mental|"
                         r"comunidades?\s+terap[êe]uticas?|cl[íi]nicas?\s+(?:de\s+)?(?:reabilita[çc][ãa]o|recupera[çc][ãa]o|"
                         r"desintoxica[çc][ãa]o|depend[êe]ncia\s+qu[íi]mica)|leitos?\s+de\s+(?:desintoxica[çc][ãa]o|sa[úu]de\s+mental|"
                         r"psiquiatria)|hospita(?:l|is)\s+psiqui[áa]tricos?)")
#: Doenças, condições, deficiências, tratamentos e procedimentos de saúde. Cada item é uma expressão
#: regular; variações de gênero, número e acentuação estão incluídas na própria expressão.
DOENCAS = (
    # Formas longas que começam como termos mais curtos da lista (a alternativa que casa primeiro
    # prevalece). Deficiência abreviada ("PcD (def. auditiva bilateral)", "def. visual").
    r"(?-i:PcD|PCD|PNE)\s*\(\s*(?:def\.?|defici[êe]ncia)\s+(?:visual|auditiva|f[íi]sica|intelectual|mental|m[úu]ltipla|motora)"
    r"(?:\s+(?:bilateral|unilateral|total|parcial|leve|moderada|grave|severa|profunda))*\s*\)",
    r"def\.\s+(?:visual|auditiva|f[íi]sica|intelectual|mental|m[úu]ltipla|motora)",
    # Transtorno do espectro autista com o nível de suporte ("TEA – nível 1 de suporte").
    r"(?:(?-i:TEA)|transtorno\s+do\s+espectro\s+autista)(?:\s*[–-]\s*|\s+)n[íi]vel\s+[1-3](?:\s+de\s+suporte)?",
    # Tratamento descrito pelo serviço ("consulta no CAPS", "acompanhamento quinzenal no CAPS infantojuvenil",
    # "internações em comunidade terapêutica").
    r"(?:consultas?|tratamento|acompanhamento|atendimento|acolhimento|interna[çc](?:[ãa]o|[õo]es))"
    r"(?:\s+(?:quinzena(?:l|is)|semana(?:l|is)|mensa(?:l|is)|regular(?:es)?|cont[íi]nu[oa]|sistem[áa]tic[oa]|"
    r"involunt[áa]ri[oa]s?|compuls[óo]ri[oa]s?|intensiv[oa]|ambulatorial))?\s+(?:n[oa]s?|em|pel[oa]|a[oa])\s+(?:uma?\s+)?"
    + _SERVICO_SAUDE_MENTAL,
    # Prematuridade com a idade gestacional, antes da forma curta; medicamento pela indicação ("remédio
    # controlado para pressão alta").
    r"prematur[oa]\s+(?:extrem[oa]\s+)?de\s+\d{1,2}\s+semanas",
    r"rem[ée]dios?(?:\s+controlados?)?\s+(?:pra|para)\s+(?:acalmar|dormir|ansiedade|depress[ãa]o|press[ãa]o(?:\s+alta)?|diabetes|"
    r"convuls[ãa]o|epilepsia|os\s+nervos|o\s+cora[çc][ãa]o)",
    # Parte do corpo amputada ("perna direita amputada").
    r"(?:pernas?|bra[çc]os?|p[ée]s?|m[ãa]os?|dedos?|h[áa]lux|membros?\s+(?:inferior|superior)(?:es)?)(?:\s+(?:direit|esquerd)[oa]s?)?"
    r"\s+amputad[oa]s?",
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
    # Idade gestacional em semanas ou meses, por extenso ou abreviada ("gestante de sete meses",
    # "GESTANTE 27 SEM").
    r"aborto", r"gestante(?:\s+(?:de\s+)?(?:\d{1,2}|" + _EXTENSO + r")\s+(?:semanas|sem\b\.?|meses))?",
    r"gr[áa]vida(?:\s+de\s+(?:\d{1,2}|" + _EXTENSO + r")\s+(?:semanas|meses))?", r"infertilidade", r"endometriose", r"menopausa", r"osteoporose",
    r"glaucoma", r"catarata", r"retinopatia", r"queimaduras?\s+de\s+\w+\s+grau", r"intoxica[çc][ãa]o(?:\s+agud[oa])?(?:\s+(?:alimentar|por\s+[\w-]+(?:\s+de\s+[\w-]+)?))?",
    r"hemodi[áa]lise", r"di[áa]lise", r"quimioterapia", r"radioterapia", r"transplante",
    r"mastectomia", r"histerectomia", r"bari[áa]trica", r"tratamento\s+(?:psiqui[áa]trico|psicol[óo]gico|oncol[óo]gico|"
    r"antirretroviral|hormonal)", r"f[áa]rmacos?\s+(?:hormonais|controlados|psiqui[áa]tricos)",
    r"antidepressivos?", r"ansiol[íi]ticos?", r"antipsic[óo]ticos?", r"insulinas?(?:\s+(?:glargina|nph|regular|asparte|lispro|detemir|degludeca|humana|an[áa]loga))?", r"internad[oa]",
    r"interna[çc](?:[ãa]o|[õo]es)(?:\s+(?:psiqui[áa]tricas?|hospitalar(?:es)?|involunt[áa]rias?|compuls[óo]rias?)|"
    r"\s+de\s+\d{1,3}\s+dias)?", r"internamentos?", r"uti", r"coma", r"sequelas?", r"crise\s+(?:de\s+)?(?:ansiedade|"
    r"p[âa]nico|convulsiva|epil[ée]ptica)", r"traumatismo(?:\s+craniano)?", r"fraturas?(?:\s+expostas?)?(?:\s+(?:de|d[oa]|n[oa])\s+\w+)?",
    r"condi[çc][ãa]o\s+(?:de\s+sa[úu]de|cl[íi]nica|m[ée]dica)(?:\s+pr[ée]-?existente)?", r"grupo\s+de\s+risco",
    r"comorbidades?", r"doen[çc]as?\s+(?:pr[ée]-?existentes?|cr[ôo]nicas?|raras?|graves?)",
    r"enfermidade(?:\s+(?:respirat[óo]ria|cr[ôo]nica|grave|rara))*", r"(?:pessoa|crian[çc]a|aluno|aluna|filh[oa]|dependente)\s+com\s+"
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
    r"pr[ée]-?natal(?:\s+(?:iniciado|em\s+curso|regular|irregular|atrasado|incompleto|de\s+alto\s+risco))?",
    r"fertiliza[çc][ãa]o\s+in\s+vitro", r"reprodu[çc][ãa]o\s+assistida",
    r"interromper\s+a\s+(?:gesta[çc][ãa]o|gravidez)", r"interrup[çc][ãa]o\s+(?:volunt[áa]ria\s+)?da\s+(?:gesta[çc][ãa]o|gravidez)",
    # Prematuridade do recém-nascido ("nasceu prematuro", "prematura de 34 semanas"); "prematuro"
    # sozinho também qualifica atos e contratos.
    r"(?<=\b(?:nasceu|nascid[oa]|rec[ée]m-nascid[oa]|beb[êe])\s)prematur[oa]",
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
    r"dor(?:es)?\s+(?:fortes?|cr[ôo]nicas?|intensas?|constantes?|agudas?|lombar(?:es)?|abdomina(?:l|is)|tor[áa]cicas?|"
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
    r"(?:consultas?|avalia[çc][ãa]o|acompanhamento|atendimento|tratamento)\s+(?:com|no|na|d[eo])\s+(?:o\s+|a\s+|um\s+|uma\s+)?"
    r"(?:psiquiatra|psic[óo]log[oa]|oncologista|infectologista|neurologista|neuropediatra|"
    r"cardiologista|endocrinologista|nefrologista|reumatologista|hematologista|urologista|mastologista|ortopedista|"
    r"oftalmologista|gastroenterologista|pneumologista|dermatologista|angiologista|geriatra|fonoaudi[óo]log[oa]|"
    r"psicopedagog[oa]|terapeuta\s+ocupacional|otorrinolaringologista)",
    r"avalia[çc][ãa]o\s+(?:fonoaudiol[óo]gica|oftalmol[óo]gica|psiqui[áa]trica|psicol[óo]gica|neurol[óo]gica|neuropsicol[óo]gica|"
    r"cardiol[óo]gica|audiol[óo]gica|ortop[ée]dica|psicopedag[óo]gica)",
    r"(?:acompanhamento|atendimento|tratamento|sess[õo]es|terapias?)\s+(?:com|de|em)\s+(?:fonoaudiologia|fisioterapia|psicologia|"
    r"psiquiatria|terapia\s+ocupacional|psicopedagogia|psicoterapia|hidroterapia|equoterapia)",
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
    # Episódio, crise e quadro de transtorno mental ("episódio depressivo moderado", "quadro demencial")
    r"epis[óo]dios?\s+(?:depressiv[oa]s?|man[íi]ac[oa]s?|hipoman[íi]ac[oa]s?|psic[óo]tic[oa]s?|convulsiv[oa]s?)",
    r"quadros?\s+(?:demencia(?:l|is)|depressiv[oa]s?|ansios[oa]s?|psic[óo]tic[oa]s?|convulsiv[oa]s?|febri(?:l|s))",
    # Dependência química: uso, abstinência e sinais de intoxicação alcoólica (Res. Contran 432/2013)
    r"(?:ex-?)?(?:etilista|tabagista|alcoolista)s?", r"etilismo", r"ex-?tabagismo",
    r"usu[áa]ri[oa]s?\s+de\s+(?:crack|coca[íi]na|maconha|[áa]lcool|subst[âa]ncias\s+psicoativas|drogas\s+il[íi]citas)",
    r"dependentes?\s+de\s+(?:crack|coca[íi]na|maconha|[áa]lcool|opioides?|nicotina|benzodiazep[íi]nicos)",
    r"depend[êe]ncia\s+de\s+(?:maconha|nicotina|benzodiazep[íi]nicos|tabaco)",
    r"abstin[êe]ncia(?:\s+(?:alco[óo]lica|de\s+(?:crack|coca[íi]na|[áa]lcool|drogas|nicotina|tabaco)))?",
    r"(?:odor|h[áa]lito)\s+(?:et[íi]lico|alco[óo]lico|de\s+[áa]lcool)", r"olhos\s+(?:vermelhos|avermelhados|hiperemiados)",
    r"fala\s+(?:pastosa|arrastada|enrolada|desconexa)", r"dificuldade\s+(?:de|no|para\s+manter\s+o)\s+equil[íi]brio",
    r"sinais\s+de\s+embriaguez", r"embriaguez", r"capacidade\s+psicomotora\s+alterada(?:\s+em\s+raz[ãa]o\s+da\s+influ[êe]ncia\s+de\s+"
    r"[áa]lcool(?:\s+ou\s+de\s+outra\s+subst[âa]ncia\s+psicoativa(?:\s+que\s+determine\s+depend[êe]ncia)?)?)?",
    # Licença e afastamento que enunciam o motivo de saúde; a simples duração do afastamento não é dado
    # de saúde
    # Também a forma composta das folhas de frequência ("Licença-saúde", "Licença-gestante").
    r"licen[çc]as?-(?:sa[úu]de|gestante|m[ée]dica)",
    r"licen[çc]as?\s+(?:m[ée]dicas?|para\s+tratamento\s+d[ae]\s+(?:pr[óo]pria\s+)?sa[úu]de|sa[úu]de|"
    r"por\s+motivo\s+de\s+(?:doen[çc]a|sa[úu]de)(?:\s+(?:em|de)\s+pessoa\s+da\s+fam[íi]lia|\s+pr[óo]pria)?|"
    r"por\s+acidente\s+(?:em\s+servi[çc]o|de\s+trabalho)|por\s+doen[çc]a\s+profissional)"
    r"(?:\s+para\s+(?:recupera[çc][ãa]o|tratamento)\s+d[eoa]\s+[^.;,\n()]{3,60})?",
    r"(?-i:LTS|LTSP)", r"motivos?\s+de\s+sa[úu]de\s+pr[óo]pria", r"afastamento\s+m[ée]dico(?:\s+por\s+\w+)?",
    # Sinais, sintomas e lesões descritos com a parte do corpo ("corte no supercílio direito",
    # "hematomas em membros inferiores", "dor no punho esquerdo")
    r"dor(?:es)?\s+de\s+(?:dente|ouvido|garganta|est[ôo]mago|barriga)",
    r"(?:muita\s+|forte\s+)?dor(?:es)?(?:\s+(?:intensa|forte|difusas?|aguda|cr[ôo]nica|persistente))?(?=\s+(?:[àa]\s+\w+\s+)?"
    r"(?:n[oa]s?|em|d[eoa]s?|pelo)\s)",
    r"cortes?(?:\s+(?:contus[oa]s?|profund[oa]s?|superficia(?:l|is)|recentes?))?(?=\s+(?:n[oa]s?|em)\s+(?:ambos\s+os\s+|ambas\s+as\s+|"
    r"dois\s+|duas\s+)?(?:antebra|bra[çc]o|perna|coxa|m[ãa]o|p[ée]|pulso|punho|rosto|face|superc[íi]lio|cabe[çc]a|testa|l[áa]bio|nariz|"
    r"dedo|joelho|costas|t[óo]rax|pesco[çc]o|orelha|ombro|regi[ãa]o\s+(?:(?:peri|supra|infra)?orbit|frontal|occipital|temporal|"
    r"parietal|malar|cervical|lombar|tor[áa]cica|abdominal|inguinal|gl[úu]tea|mandibular|nasal|zigom|escapular|axilar|"
    r"labial|mentoniana)))",
    r"escoria[çc](?:[ãa]o|[õo]es)", r"equimoses?(?:\s+arroxeadas?)?", r"hematomas?",
    r"edemas?", r"linfedema", r"contus(?:[ãa]o|[õo]es)", r"lacera[çc](?:[ãa]o|[õo]es)", r"pet[ée]quias", r"rigidez\s+de\s+nuca",
    r"tremor(?:es)?(?:\s+(?:discreto|fino|grosseiro|essencial|de\s+extremidades))*", r"parestesias?", r"emagrecimento",
    r"perda\s+de\s+peso", r"baixo\s+peso(?:\s+para\s+a\s+idade)?", r"tosse(?:\s+(?:seca|produtiva|persistente|cr[ôo]nica))?",
    r"febre(?:\s+(?:di[áa]ria|baixa|vespertina|ao\s+entardecer))?(?:\s+de\s+\d+(?:[.,]\d+)?\s*°\s?C)?", r"calafrios",
    r"prostra[çc][ãa]o", r"cansa[çc]o(?:\s+(?:ao\s+acordar|extremo|aos\s+esfor[çc]os))?", r"sono\s+n[ãa]o\s+reparador",
    r"(?:tristeza\s+e\s+)?choro\s+f[áa]cil", r"pesadelos(?:\s+recorrentes)?", r"(?:epis[óo]dios\s+de\s+)?enurese(?:\s+noturna)?",
    # A dificuldade de ver, ouvir, ler ou escrever inclui o objeto ("dificuldade para enxergar a lousa").
    r"encoprese", r"dificuldade\s+(?:para|de)\s+(?:dormir|engolir|respirar|(?:enxergar|ouvir|ler|escrever)(?:\s+(?:o|a|os|as)\s+"
    r"[\wà-ú-]+)?|falar|se\s+concentrar|manter\s+a\s+aten[çc][ãa]o(?:\s+em\s+[\w-]+(?:\s+[\w-]+)?)?)", r"lentid[ãa]o\s+(?:na|de|para)\s+\w+(?:\s+e\s+na\s+\w+)?",
    r"incontin[êe]ncia\s+(?:urin[áa]ria|fecal|esfincteriana)", r"d[ée]ficit\s+(?:auditivo|visual|cognitivo|motor|"
    r"de\s+ganho\s+ponderal)", r"pico\s+de\s+press[ãa]o(?:\s+arterial)?", r"massagem\s+card[íi]aca",
    r"reanima[çc][ãa]o\s+(?:cardiopulmonar|card[íi]aca)", r"stents?",
    r"transfus(?:[ãa]o|[õo]es)(?:\s+de\s+(?:hemoderivados|hemocomponentes|plaquetas|plasma|concentrado\s+de\s+hem[áa]cias|"
    r"\d+\s+unidades(?:\s+de\s+concentrado\s+de\s+hem[áa]cias)?(?:\s+e\s+\d+\s+de\s+plasma)?))?",
    r"carga\s+viral\s+(?:indetect[áa]vel|detect[áa]vel|suprimida)",
    r"interna[çc][ãa]o\s+em\s+(?:unidade\s+(?:coronariana|de\s+terapia\s+intensiva)|(?-i:UTI)|enfermaria|leito\s+\w+)",
    # O exame pericial só requisitado ("Requisitado exame de corpo de delito ao IML") é providência policial,
    # e não dado de saúde da vítima.
    r"(?<!\b(?:requisitad[oa]|requisi[çc][ãa]o\s+d[eo]|solicitad[oa]|encaminhad[oa]\s+a[oa]?|guia\s+para(?:\s+o)?)\s{1,3})"
    r"exame\s+de\s+corpo\s+de\s+delito", r"(?:atendimento|acompanhamento)\s+(?:psicol[óo]gico|psicopedag[óo]gico|"
    r"nefrol[óo]gico|cardiol[óo]gico|oncol[óo]gico|neurol[óo]gico|ortop[ée]dico|ambulatorial)",
    r"terapia\s+(?:antirretroviral|fonoaudiol[óo]gica|aurioral|comportamental|cognitivo-comportamental|"
    r"de\s+reposi[çc][ãa]o\s+hormonal|renal\s+substitutiva|intensiva)", r"(?-i:AASI)",
    r"aparelhos?\s+de\s+amplifica[çc][ãa]o\s+sonora(?:\s+individual)?", r"palmilhas?\s+ortop[ée]dicas?",
    r"(?:cart[ãa]o|caderneta)\s+de\s+vacina[çc][ãa]o\s+(?:incomplet[oa]|atrasad[oa]|desatualizad[oa])",
    r"vacina[çc][ãa]o\s+(?:em\s+dia|incompleta|atrasada)", r"esquema\s+(?-i:[A-Z]{2,6})(?:\s+(?:supervisionado|b[áa]sico))?",
    r"alimenta[çc][ãa]o\s+(?:exclusiva\s+)?por\s+sonda(?:\s+\w+)?", r"dietas?\s+(?:pastosa|l[íi]quida|zero|hiposs[óo]dica|"
    r"hipoglic[íi]dica|adaptada|branda|sem\s+gl[úu]ten|sem\s+lactose)",
    r"suplementa[çc][ãa]o(?!\s+or[çc]ament)(?:\s+(?:nutricional|alimentar|vitam[íi]nica|de\s+(?:ferro|c[áa]lcio|zinco|"
    r"vitaminas?(?:\s+(?-i:[A-K]\d{0,2})(?:\s*,\s*(?-i:[A-K]\d{0,2}))*(?:\s+e\s+(?-i:[A-K]\d{0,2}))?)?)))?",
    r"incapacidade\s+(?:laborativa|laboral|funcional|f[íi]sica|total|parcial|permanente|tempor[áa]ria|definitiva)"
    r"(?:\s+(?:e\s+)?(?:total|parcial|permanente|tempor[áa]ria|definitiva))*(?:\s+para\s+(?:o\s+)?(?:trabalho|"
    r"(?:o\s+)?exerc[íi]cio\s+d[oa]\s+(?:cargo|fun[çc][ãa]o)|a\s+atividade\s+habitual(?:\s+de\s+\w+)?))?",
    r"(?:temporariamente|definitivamente|permanentemente|totalmente|parcialmente)\s+incapaz(?:\s+para\s+(?:o\s+)?"
    r"(?:trabalho|exerc[íi]cio\s+d[oa]\s+(?:cargo|fun[çc][ãa]o)))?",
    r"impedimento\s+de\s+longo\s+prazo(?:\s+de\s+natureza\s+\w+)?(?:,\s+de\s+grau\s+\w+)?",
    r"grau\s+de\s+(?:depend[êe]ncia|incapacidade(?:\s+f[íi]sica)?)\s+(?-i:[IVX]{1,3}\b|\d)", r"grau\s+\d\s+de\s+incapacidade",
    r"assist[êe]ncia\s+permanente(?:\s+(?:de\s+(?:outra\s+pessoa|terceiros)|para\s+as\s+atividades\s+de\s+vida\s+di[áa]ria))?",
    r"supervis[ãa]o\s+cont[íi]nua(?:\s+de\s+terceiros)?", r"atividades\s+(?:b[áa]sicas\s+|instrumentais\s+)?de\s+vida\s+di[áa]ria",
    r"comprometimento\s+(?:da\s+capacidade\s+de\s+\w+|cognitivo|funcional|motor)",
    # Saúde mental, sintoma e comportamento em linguagem leiga, como aparecem em relatos, falas
    # transcritas e registros de escola ou de assistência social ("escuta vozes", "não dorme", "parou de
    # comer", "se corta nos braços").
    r"(?:escuta|escutava|escutando|ouve|ouvia|ouvindo)\s+(?:umas?\s+|as\s+|algumas\s+)?vozes"
    r"(?:\s+(?:mandando|dizendo|que\s+(?:o\s+|a\s+|lhe\s+|me\s+)?(?:mandam|mandavam|dizem|diziam))\s+[^.;,\n]{2,40}?(?=[.;,\n]|$))?",
    r"(?:v[êe]|via|vendo)\s+vultos", r"fala(?:va)?\s+sozinh[oa]",
    r"n[ãa]o\s+(?:dorme|dormia|consegue\s+dormir|conseguia\s+dormir|se\s+alimenta(?:va)?|toma\s+banho|sai\s+do\s+quarto|"
    r"sa[íi]a\s+do\s+quarto|controla(?:va)?\s+(?:os\s+)?esf[íi]ncteres|(?:fala|forma|articula)\s+(?:frases|palavras)"
    r"(?:\s+(?:completas|inteiras|simples))?|enxerga(?:va)?\s+bem|ouve\s+bem)",
    r"(?:parou|deixou)\s+de\s+(?:comer(?:\s+direito)?|dormir|tomar\s+banho|se\s+alimentar|tomar\s+(?:a\s+|os\s+|as\s+)?"
    r"(?:medica[çc][ãa]o|medica[çc][õo]es|rem[ée]dios?))",
    r"chora(?:va)?\s+(?:escondid[oa]|muito|o\s+tempo\s+todo|todos\s+os\s+dias|sem\s+motivo|com\s+frequ[êe]ncia)",
    r"(?:vem\s+)?se\s+(?:cort|mord|machuc|arranh)(?:a|e|ava|ou|ando)", r"tapa(?:va)?\s+os\s+ouvidos",
    r"(?:risco\s+de\s+)?autoexterm[íi]nio", r"autoles(?:[ãa]o|[õo]es|iv[oa]s?)", r"viol[êe]ncia\s+autoprovocada",
    r"comportamentos?\s+(?:autolesivos?|suicidas?|autodestrutivos?)",
    r"(?:pensa|pensava|pensou|pensamentos?)\s+em\s+(?:se\s+matar|suic[íi]dio|tirar\s+a\s+pr[óo]pria\s+vida)",
    r"crises?\s+de\s+(?:choro|agressividade|aus[êe]ncia|desmaio|falta\s+de\s+ar)",
    # Uso de substância por verbo ou perífrase ("cheirava loló", "vive tomando cachaça", "usuário de pedra");
    # "pedra" e "pó" só depois de verbo de uso ou de "usuário de".
    r"(?:uso|consumo)(?:\s+(?:di[áa]rio|abusivo|frequente|eventual|recreativo|problem[áa]tico|nocivo|habitual|pesado|"
    r"regular|irregular|cont[íi]nuo|prejudicial|intenso))?\s+de\s+" + _SUBSTANCIA + r"(?:\s+e\s+(?:de\s+)?" + _SUBSTANCIA + r")?",
    r"(?:(?:usu[áa]ri[oa]|dependente|viciad[oa])\s+(?:de|em)|doid(?:[ãa]o|ona)\s+de|"
    r"(?:(?:vive|anda|fica|passa\s+o\s+dia)\s+)?(?:fuma|fumava|fumando|fumou|cheira|cheirava|cheirando|cheirou|usa|usava|usando|"
    r"usou|consome|consumia|consumindo|injeta|injetava|bebe|bebia|bebendo|toma|tomava|tomando)(?:\s+muit[oa]|\s+bastante)?)"
    r"\s+(?:pedra|p[óo]|" + _SUBSTANCIA + r")",
    r"beb(?:e|ia|endo)(?=\s+(?:todos\s+os\s+dias|diariamente|todo\s+dia|muito|demais|com\s+frequ[êe]ncia|"
    r"excessivamente|desde\s+que))",
    r"(?:segue|seguia|frequenta|frequentava|acompanhad[oa])\s+(?:n[oa]|pel[oa]|a[oa])\s+" + _SERVICO_SAUDE_MENTAL,
    r"(?:passou|ficou|permaneceu)\s+(?:a\s+noite\s+|uma\s+noite\s+|\d{1,2}\s+horas\s+|" + _EXTENSO + r"\s+(?:dias|horas)\s+)?"
    r"em\s+observa[çc][ãa]o(?:\s+(?:hospitalar|m[ée]dica))?",
    r"fila\s+(?:d[oe]|para\s+(?:o\s+)?)\s*transplantes?(?:\s+de\s+\w+)?",
    # Termos coloquiais, dispositivos e atos assistenciais ligados à pessoa.
    # "Bombinha" de asma, e não o artefato pirotécnico ("soltar bombinhas", "bombinhas juninas").
    r"(?<!\b(?:solta|soltam|soltar|soltou|soltava|soltavam|estoura|estouram|estourar|estourou|venda\s+de|fogos\s+e)\s)"
    r"bombinhas?(?!\s+(?:juninas?|de\s+s[ãa]o\s+jo[ãa]o|e\s+fogos))(?:\s+(?:de|para)\s+(?:asma|falta\s+de\s+ar))?",
    r"nebuliza(?:dor(?:es)?|[çc][ãa]o|[çc][õo]es)", r"inaladores?",
    r"glicos[íi]metros?", r"fitas?\s+(?:de\s+glicemia|reagentes?\s+para\s+glicemia)", r"lancetas",
    r"(?:seringas?|canetas?|agulhas?)\s+(?:de|para)\s+insulina", r"(?<!\bsalas?\s+(?:de\s+)?)curativos?",
    r"feridas?(?:\s+(?:abertas?|infectadas?|operat[óo]rias?|cr[ôo]nicas?|cir[úu]rgicas?))?",
    r"abafador(?:es)?\s+de\s+ru[íi]dos?", r"lupas?\s+eletr[ôo]nicas?",
    r"[óo]culos\s+(?:para|de)\s+(?:miopia|grau|leitura|astigmatismo|hipermetropia)",
    r"prova\s+tubercul[íi]nica", r"hormonioterapia", r"hormoniza[çc][ãa]o", r"osteoss[íi]ntese(?:\s+com\s+fixador(?:\s+externo)?)?",
    r"profilaxia\s+pr[ée]-exposi[çc][ãa]o", r"perda\s+de\s+sensibilidade",
    r"atraso\s+(?:n[ao]|d[ao]|de)\s+(?:fala|linguagem|desenvolvimento\s+(?:neuro)?psicomotor|desenvolvimento\s+global|marcha)",
    r"c[óo]licas?\s+(?:biliar(?:es)?|renal|renais|nefr[ée]ticas?)", r"condi[çc][ãa]o\s+neurol[óo]gica",
    r"marcas?\s+(?:roxas?|de\s+(?:agress[ãa]o|espancamento|mordida|enforcamento|estrangulamento|queimadura))",
    r"esquema\s+vacinal(?:\s+(?:incompleto|em\s+atraso|atrasado|desatualizado|em\s+dia|completo|interrompido))?",
    r"(?:retomada|abandono|interrup[çc][ãa]o)\s+d[oa]\s+tratamento(?!\s+d[eoa]s?\s+(?:[áa]gua|esgoto|dados|res[íi]duos|efluentes|lixo))",
    r"acuidade\s+visual\s+(?:de\s+)?\d{1,2}/\d{2,3}(?:\s+n[oa]\s+olho\s+(?:direito|esquerdo))?"
    r"(?:\s+e\s+\d{1,2}/\d{2,3}(?:\s+n[oa]\s+(?:olho\s+)?(?:direito|esquerdo))?)?",
    r"comprimidos?\s+(?:de|para|pra)\s+(?:press[ãa]o|dormir|diabetes|depress[ãa]o|ansiedade)",
    # Siglas clínicas de tratamento: terapia antirretroviral, profilaxia pré-exposição ao HIV, tratamento
    # diretamente observado da tuberculose e poliquimioterapia da hanseníase.
    r"(?-i:TARV|PrEP|TDO|PQT)(?:/(?-i:MB|PB))?",
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
           # A expressão não atravessa oração relativa ou adverbial ("faz tratamento para HIV na Unidade X e que
           # perdeu duas consultas"), que já não descreve a condição; a coordenação de condições ("diabetes e
           # hipertensão") continua na expressão.
           r"\s+(?:(?!\s(?:e\s+que|onde|quando|mas|porque|pois|enquanto)\s)[^\n.;,()]){3,60}", 0.9, camada=CONTEXTUAL,
           nome="saude:frase"),
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
_GRAVIDADE = (r"sever[oa]s?|graves?|leves?|moderad[oa]s?|parcia(?:l|is)|totais|total|cr[ôo]nic[oa]s?|agud[oa]s?|avan[çc]ad[oa]|inicial|"
              r"constantes?|intens[oa]s?|frequentes?|"
              r"terminal|maligna|maligno|benign[oa]|descompensad[oa]|persistente|refrat[áa]ri[oa]|"
              r"profund[oa]|bilateral|cong[êe]nit[oa]|heredit[áa]ri[oa]|remitente(?:[- ]recorrente)?|recorrente|"
              r"(?:em\s+)?est[áa]gio\s+\w+|tipo\s+[12]|de\s+grau\s+\w+|positiv[oa]|negativ[oa]")
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
                   r"pesco[çc]o|test[íi]culos?|cr[âa]nio|dedos?|superc[íi]lios?|sobrancelhas?|testa|face|rosto|nariz|f[íi]bula|"
                   r"[úu]mero|ulna|h[áa]lux|"
                   r"l[áa]bios?|orelhas?|nuca|t[óo]rax|abd[ôo]men|abdome|costas|antebra[çc]os?|coxas?|panturrilhas?|"
                   r"calcanhar(?:es)?|costelas?|clav[íi]cula|n[áa]degas?|tronco|gengivas?|"
                   r"membros?\s+(?:superiores|inferiores|superior|inferior)|regi[ãa]o\s+(?:(?:peri|supra|infra)?orbit[áa]ria|"
                   r"(?:peri|supra|infra)?orbital|malar|frontal|"
                   r"occipital|temporal|parietal|lombar|cervical|tor[áa]cica|abdominal|inguinal|gl[úu]tea|sacral|perineal|"
                   r"genital|palmar|plantar|dorsal|axilar|mandibular|nasal|zigom[áa]tica|epig[áa]strica|umbilical|escapular|"
                   r"femoral|tibial|popl[íi]tea|cubital|deltoide[a]?)")
#: Lado do corpo após a parte ("punho esquerdo", "membros inferiores bilateralmente").
_LATERALIDADE = r"(?:\s+(?:(?:direit|esquerd)[oa]s?|bilateral(?:mente)?|[àa]\s+(?:direita|esquerda)))?"
_QUALIFICADOR = (r"(?:\s+(?:" + _GRAVIDADE + "|" + _TIPO_CLINICO + r"|(?:d[eoa]s?|n[oa]s?|em)\s+(?:ambos\s+os\s+|ambas\s+as\s+|"
                 r"dois\s+|duas\s+)?(?:" + _PARTE_DO_CORPO + r")" + _LATERALIDADE
                 # Outra parte do corpo coordenada à primeira ("no joelho direito e no antebraço esquerdo",
                 # "de tíbia e fíbula direitas").
                 + r"|e\s+(?:(?:d[eoa]s?|n[oa]s?|em)\s+)?(?:" + _PARTE_DO_CORPO + r")" + _LATERALIDADE + r"))")
#: Sigla entre parênteses logo após o nome ("esclerose lateral amiotrófica (ELA)").
_SIGLA = r"(?:\s*\((?-i:[A-Z][A-Z0-9]{1,6}(?:[/-][A-Z0-9]{1,6})?)\))?"
_DOENCA = r"(?:" + "|".join(DOENCAS) + r")" + _QUALIFICADOR + r"{0,3}" + _SIGLA
#: Termo do léxico de saúde, para conferir achados do classificador treinado.
_TERMO_SAUDE = re.compile(r"(?:" + "|".join(DOENCAS) + r")" + _QUALIFICADOR + r"{0,3}", re.IGNORECASE)
#: Sal ou éster antes do nome do fármaco ("cloridrato de metformina", "carbonato de lítio").
_SAL = (r"(?:(?:cloridrato|dicloridrato|sulfato|maleato|besilato|fumarato|hemifumarato|succinato|tartarato|citrato|"
        r"acetato|fosfato|carbonato|valerato|propionato|dipropionato|mesilato|bromidrato|oxalato|pamoato|decanoato|"
        r"furoato)\s+de\s+)?")
#: Classes terapêuticas pelo sufixo da DCB: anticorpos monoclonais (-mabe), proteínas de fusão
#: (-cepte), inibidores de quinase (-tinibe, -ciclibe), gliflozinas, gliptinas, sartanas, estatinas,
#: inibidores da bomba de prótons (-prazol), benzodiazepínicos (-azepam, -zolam), antidepressivos
#: (-xetina, -triptilina, -pramina), antipsicóticos (-peridona, -tiapina, -zapina, -piprazol),
#: betabloqueadores (-olol), inibidores da ECA (-pril), di-hidropiridinas (-dipino), quinolonas
#: (-floxacino), tetraciclinas (-ciclina), macrolídeos e aminoglicosídeos (-micina), penicilinas
#: (-cilina), tiazídicos (-tiazida), heparinas (-parina), bisfosfonatos (-dronato), antieméticos
#: (-setrona), antifúngicos (-conazol), anti-inflamatórios (-profeno) e antirretrovirais (-vudina,
#: -navir, -tegravir, -previr, -asvir, -buvir).
_SUFIXO_FARMACO = (r"[a-záéíóúâêôãõç]{3,}(?:mabe|cepte|tinibe|ciclibe|gliflozina|gliptina|sartana|statina|prazol|"
                   r"azepam|zolam|xetina|triptilina|pramina|peridona|tiapina|zapina|piprazol|olol|pril|dipino|"
                   r"floxacino|ciclina|micina|cilina|tiazida|parina|dronato|setrona|conazol|profeno|vudina|navir|"
                   r"tegravir|previr|asvir|buvir)")
#: Sal ou forma após o nome ("losartana potássica", "dipirona sódica") e forma de liberação ou de uso
#: ("metilfenidato de liberação prolongada", "carbamazepina de uso contínuo").
_FORMA = (r"(?:\s+(?:pot[áa]ssic[oa]|s[óo]dic[oa]|c[áa]lcic[oa]|magn[ée]sic[oa]|monoidratad[oa]|di-?hidratad[oa]))?"
          r"(?:\s+de\s+(?:uso\s+cont[íi]nuo|libera[çc][ãa]o\s+(?:prolongada|controlada|modificada|imediata)))?")
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
    Padrao("SAUDE", r"\btratamentos?[ \t]+" + _TRATAMENTO_NAO_SAUDE + r"(?:\w+[ \t]+)?(?:de|para|contra|da|do)[ \t]+"
           + _OBJETO_NAO_SAUDE + r"[^\n.;,()]{3,50}", 0.75, camada=SEMANTICA, nome="saude:tratamento-de"),
]
#: Vacinas do calendário nacional pelo nome ou pela sigla, e a dose aplicada ("TRÍPLICE VIRAL D1",
#: "Meningo C – reforço", "HPV 2ª dose").
_VACINA = (r"(?:tr[íi]plice\s+(?:viral|bacteriana)|tetraviral|pentavalente|hexavalente|meningo(?:c[óo]cica)?(?:\s*(?-i:C|ACWY|B)\b)?"
           r"(?:\s+conjugada)?|pneumo(?:c[óo]cica)?(?:\s*(?:10|13|23)(?:-?valente)?)?|hepatite\s+(?-i:A|B)\b|febre\s+amarela|"
           r"rotav[íi]rus|varicela|influenza|covid(?:-?19)?|poliomielite|(?-i:VIP|VOP|VORH|BCG|HPV\d*|dTpa|dT|DTP|SCR|SCRV|"
           r"VZ|MenC|MenACWY|VPC10|VPC13))")
_DOSE_VACINA = (r"(?:(?-i:D[1-5]|DU|REF|R[12])|[1-5][ªa°º]\s+dose|dose\s+(?:[úu]nica|de\s+refor[çc]o|zero|inicial|[1-5])|"
                r"refor[çc]o)")
SAUDE_SEMANTICA += [
    Padrao("SAUDE", r"\b" + _VACINA + r"\s*(?:[–-]\s*)?" + _DOSE_VACINA + r"(?!\w)", 0.8, camada=SEMANTICA,
           nome="saude:vacina-dose"),
    # Resultado de exame citado fora do registro clínico ("o VDRL saiu 1:32", "anti-HIV reagente").
    Padrao("SAUDE", r"\b(?-i:VDRL|FTA-ABS|anti-HIV|HBsAg|anti-HCV|PSA|HbA1c)\s+(?:(?:saiu|deu|foi|veio|resultou)\s+)?"
                    r"(?:(?:n[ãa]o\s+)?reagente|positivo|negativo|detect[áa]vel|indetect[áa]vel|1\s*:\s*\d{1,4})\b", 0.8,
           camada=SEMANTICA, nome="saude:resultado"),
    # Código da CID sem pontuação ("CID 10 F84 0"), como em formulários digitados e em texto digitalizado.
    Padrao("SAUDE", r"\bCID[\s-]?1[01]\s+(?-i:[A-TV-Z]\d{2})(?:[\s.]\d)?\b", 0.9, camada=CONTEXTUAL, nome="saude:cid-sem-ponto"),
    # Campo de ficha cujo valor é dado de saúde da pessoa da ficha ("Alergias: dipirona e amendoim", "Tipo
    # de deficiência: visual"). O valor vai até o próximo rótulo, o separador de colunas ou o fim da linha;
    # campo vazio, com opções a marcar ou respondido com "não" fica de fora.
    # O rótulo abre o campo (início de linha ou depois de separador), para não confundir com a contagem de
    # um grupo ("pessoas com deficiência: 312").
    Padrao("SAUDE", r"(?:^|(?<=[|;\t]|[ \t]{2}))[ \t]*(?:alergias?|tipo\s+de\s+defici[êe]ncia|defici[êe]ncias?|"
                    r"condi[çc][ãa]o\s+de\s+sa[úu]de|condi[çc][õo]es\s+de\s+sa[úu]de|problemas?\s+de\s+sa[úu]de|"
                    r"doen[çc]as?\s+cr[ôo]nicas?|restri[çc][ãa]o\s+alimentar)"
                    r"(?:\s*\([^()\n]{1,20}\))?\s*:\s*(?!(?:n[ãa]o|nenhum[a]?|nega|sem|n/?a|---?|—)\b)(?!\d[\d.,]*\s*(?:[|;]|$))"
                    r"([^\s:|;(\[_][^\n:|;]{1,80}?)(?=[ \t]+(?-i:[A-ZÀ-Ú])[\wÀ-ú.]*(?:[ \t]+[\wÀ-ú.]+)?[ \t]*:|[ \t]{2,}|[ \t]*[|;]|[ \t]*$)", 0.8,
           camada=CONTEXTUAL, grupo=1, nome="saude:campo"),
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
               r"(?:luto|luta|lutou)\s+contra|venho\s+sofrendo\s+(?:de|com)|faleceu\s+(?:de|por)|"
               # Relato da própria pessoa ou do técnico sobre ela ("relata tuberculose", "queixa-se de dor de
               # dente") e uso de dispositivo ("usa órtese", "usa nebulizador").
               r"relata|relatou|refere|referiu|queixa-se\s+de|queixou-se\s+de|se\s+queixa\s+de|usa|usava|"
               # Verbo que só atribui o tratamento ("concluiu tratamento de hanseníase").
               r"(?:conclu[íi]u|iniciou|interrompeu|abandonou|retomou)(?:\s+em\s+\d{4})?(?=\s+(?:o\s+)?tratamento\b)|"
               # Estado atual da pessoa ("está gestante de 20 semanas", "ficou internada", "encontra-se acamada").
               r"est(?:á|ava|eve)|fic(?:ou|ava)|encontra-se|permanece")
_COMPLEMENTO = (r"(?:\s+(?:um|uma|o|a))?(?:\s+(?:quadro|diagn[óo]stico|suspeita|hist[óo]rico|caso|crise|crises)"
                r"(?:\s+(?:cl[íi]nico|grave|severo|preliminar|confirmado))?\s+de)?")
SAUDE_CONTEXTUAL.append(
    Padrao("SAUDE", r"\b(?:" + _ATRIBUICAO + r")" + _COMPLEMENTO + r"\s{1,3}((?:(?:o\s+)?tratamento\s+(?:de|para|contra)\s+)?"
           + _DOENCA + r")(?!\w)", 0.9,
           camada=CONTEXTUAL, grupo=1, nome="saude:possui", sobrepostos=True))
# Registro clínico de um caso ("prontuário referente à intoxicação…", "laudo de autismo", "quadro de
# malária grave") e campo de formulário ("Condição clínica: paralisia cerebral"): referem-se a uma
# pessoa determinada mesmo sem pronome na frase.
SAUDE_CONTEXTUAL.append(
    Padrao("SAUDE", r"\b(?:(?:laudos?|atestados?|prontu[áa]rios?)(?:\s+(?:m[ée]dicos?|cl[íi]nicos?))?\s+"
                    r"(?:de|sobre|referentes?\s+(?:a|à|ao)|que\s+(?:atesta|comprova|indica))(?:\s+(?:o|a|um|uma))?|"
                    r"quadro\s+(?:cl[íi]nico\s+)?(?:grave\s+)?de|crise\s+de|"
                    r"(?:condi[çc][ãa]o\s+cl[íi]nica|quadro\s+cl[íi]nico|diagn[óo]stico|hip[óo]tese\s+diagn[óo]stica|"
                    r"patologia|doen[çc]a|comorbidades?|enfermidade)\s*:|"
                    # Causa da morte registrada em certidão ou declaração de óbito.
                    r"causa\s+(?:da\s+morte|do\s+[óo]bito|mortis)(?:\s*:|\s+(?:foi|[ée]|era))?)\s{0,3}(" + _DOENCA + r")(?!\w)", 0.9,
           camada=CONTEXTUAL, grupo=1, nome="saude:registro-clinico", sobrepostos=True))
# Medicamento precedido de verbo de uso ou prescrição ("tomo fluoxetina", "faz uso de insulina NPH").
SAUDE_CONTEXTUAL.append(
    Padrao("SAUDE", r"(?<=\b(?:tomo|toma|tomam|tomando|tomava|fa[çz]o\s+uso\s+de|faz\s+uso\s+de|fazendo\s+uso\s+de|"
                    r"uso\s+cont[íi]nuo\s+de|receitou|prescreveu|prescrit[oa]s?|receitad[oa]s?|usa|usava)\s{1,3}(?:[oa]\s+)?|"
                    # Campo de ficha ("Medicação contínua: risperidona", "Medic. contínuo: …").
                    r"\b(?:medica[çc](?:[ãa]o|[õo]es)|medicamentos?|medic\.|rem[ée]dios?)\s*(?:cont[íi]nu[oa]s?|em\s+uso|"
                    r"de\s+uso\s+cont[íi]nuo|controlad[oa]s?)?\s*:\s*)"
           + _MEDICAMENTO + r"\b", 0.9, camada=CONTEXTUAL, nome="saude:uso-medicamento"))
# Tratamento com o medicamento nomeado ("tratamento com penicilina benzatina").
SAUDE_SEMANTICA.append(
    Padrao("SAUDE", r"\btratamentos?\s+com\s+" + _MEDICAMENTO + r"\b", 0.8, camada=SEMANTICA, nome="saude:tratamento-com"))
# Lista de códigos da CID após rótulo de diagnóstico ("Diagnósticos de alta: E11.5; M86.1; Z89.4",
# "HD: F10.2 / I10 / K70.0?", "CID-10 da causa básica: O72.1"): o rótulo atribui os códigos à pessoa
# examinada. O código entra com o "?" de hipótese diagnóstica.
_CODIGO_CID_LISTA = r"(?-i:[A-TV-Z]\d{2}(?:\.\d{1,2})?|[1-9][A-HJ-NP-Z][0-9A-HJ-NP-Z]{2}(?:\.[0-9A-HJ-NP-Z]{1,2})?)\??"
SAUDE_CONTEXTUAL.append(
    Padrao("SAUDE", r"\b(?:diagn[óo]sticos?(?:\s+(?:de\s+alta|principal|principais|secund[áa]rios?|definitivos?|finais?|de\s+base))?|"
                    r"hip[óo]teses?\s+diagn[óo]sticas?|(?-i:HD|HDs)|(?-i:CID)(?:-1[01])?(?:\s+d[aoe]s?(?:\s+\w+){1,2})|"
                    r"causas?\s+b[áa]sicas?)\s*:\s*(" + _CODIGO_CID_LISTA + r"(?:\s*(?:;|,|/|\be\b)\s*" + _CODIGO_CID_LISTA
           + r")*)(?!\w)(?!\.\d)", 0.9, camada=CONTEXTUAL, grupo=1, nome="saude:cid-lista"))
# Código da CID no início de linha seguido da descrição ("F33.2 – transtorno depressivo recorrente"),
# forma de listagem de diagnósticos em laudos e prontuários.
SAUDE_CONTEXTUAL.append(
    Padrao("SAUDE", r"^[ \t]*(?:[-–•]\s*)?(?-i:[A-TV-Z]\d{2}\.\d{1,2}|[1-9][A-HJ-NP-Z][0-9A-HJ-NP-Z]{2}\.[0-9A-HJ-NP-Z]{1,2})"
                    r"\s*[–—-]\s*[^\n;]{3,120}", 0.9, camada=CONTEXTUAL, nome="saude:cid-descricao"))

# --------------------------------------------------------------------------- Saúde: registro clínico
# Formas próprias do registro clínico e pericial de uma pessoa: resultado de exame, sinal vital e
# medida, escala clínica, posologia, achado do exame físico ou psíquico, gestação e parto,
# funcionalidade e restrições recomendadas por junta médica. Em normas, protocolos e boletins as mesmas
# formas descrevem critérios ("glicemia de jejum acima de 126 mg/dL"), e não uma pessoa; por isso estes
# achados só são considerados em documento centrado numa pessoa identificada (ver
# :func:`contexto_documental`). A confiança (0,65) fica abaixo da dos termos de :data:`SAUDE_SEMANTICA`,
# para que um achado mais longo não absorva, na remoção de duplicatas do Presidio, o termo que contém.

#: Número de achados de saúde a partir do qual um documento centrado em pessoa é tratado como registro
#: clínico, ainda que sem título ou seções de prontuário.
ACHADOS_DE_REGISTRO_CLINICO = 8
#: Prefixo da origem dos achados de registro clínico, descartados fora de documento centrado em pessoa.
ORIGEM_CLINICA = "saude:clinico:"
#: Prefixo dos achados que só valem dentro de registro clínico ou pericial (laudo, prontuário, ficha de
#: notificação): nome de exame, campo de formulário clínico, achado do exame físico e termo pelo sufixo.
#: Num ofício ou num boletim de ocorrência, "Natureza:" e "Procedimento:" não descrevem condição de saúde.
ORIGEM_REGISTRO = ORIGEM_CLINICA + "registro:"
_NUM = r"\d+(?:[.,]\d+)*"
#: Unidades de exames laboratoriais, sinais vitais e funções orgânicas.
_UNIDADE_CLINICA = (r"(?:(?:mg|g|ng|pg|µg|mcg|mEq|mmol|µmol|mU|mUI|µUI|UI|U|c[ée]lulas|c[ée]l)/(?:dL|L|mL|mm³|mm3|g|kg|24\s?h|min)"
                    r"|/mm³|/mm3|/µL|mmHg|cmH2O|bpm|irpm|ipm|kg/m²|kg/m2|°C|ºC|dBNA|dB\s?NA|dB|fL|mL/min|L/min|mm/h)")
#: Analitos de exames laboratoriais. As siglas diferenciam maiúsculas ("PCR", "TGO").
_ANALITO = (r"(?:hemoglobina(?:\s+glicada)?|hemat[óo]crito|leuc[óo]citos|neutr[óo]filos|linf[óo]citos|eosin[óo]filos|plaquetas|"
            r"glicemia(?:\s+(?:de\s+jejum|capilar|p[óo]s-prandial|casual))?|glicose|creatinina|ureia|s[óo]dio|pot[áa]ssio|"
            r"magn[ée]sio|fosfatase\s+alcalina|bilirrubina(?:\s+(?:total|direta|indireta))?|albumina|prote[íi]nas\s+totais|"
            r"prote[íi]na\s+C\s+reativa|ferritina|ferro\s+s[ée]rico|vitamina\s+(?:B12|D)|colesterol(?:\s+(?:total|LDL|HDL))?|"
            r"triglic[ée]r[íi]deos|[áa]cido\s+[úu]rico|troponina|lactato|amilase|lipase|litemia|clearance(?:\s+de\s+creatinina)?|"
            r"taxa\s+de\s+filtra[çc][ãa]o\s+glomerular|microalbumin[úu]ria|protein[úu]ria|elastase\s+fecal|cloreto|"
            r"carga\s+viral(?:\s+d[oa]\s+[\w-]+)?|contagem\s+de\s+(?:CD4|linf[óo]citos\s+T\s+CD4)|"
            r"(?-i:Hb|HbA1c|Ht|TGO|TGP|AST|ALT|GGT|INR|RNI|TAP|TTPA|PCR|VHS|TSH|T4|T4L|T4\s+livre|T3|LDL|HDL|CK|CK-MB|CPK|"
            r"BNP|PSA|CD4|VCM|HCM|CHCM|RDW|TFG|beta-HCG|HBsAg|anti-HCV|anti-HIV|anti-HBs|VDRL|FTA-ABS))")
_RESULTADO = (rf"(?:{_NUM}\s*(?:%|{_UNIDADE_CLINICA})?|(?:n[ãa]o\s+)?reagentes?|(?:n[ãa]o\s+)?detectad[oa]|"
              r"(?:in)?detect[áa]vel|positiv[oa]|negativ[oa])")
#: Sinais vitais e medidas antropométricas.
_SINAL_VITAL = (r"(?:(?-i:PA|PAS|PAD|PAM|FC|FR|SpO2|SatO2|Tax|HGT|IMC|PIO|PC|CA)|press[ãa]o\s+arterial(?:\s+(?:sist[óo]lica|diast[óo]lica))?|"
                r"frequ[êe]ncia\s+(?:card[íi]aca|respirat[óo]ria)|satura[çc][ãa]o(?:\s+(?:perif[ée]rica\s+)?(?:de\s+)?(?:O2|oxig[êe]nio))?|"
                r"temperatura(?:\s+axilar)?|peso|altura|estatura|per[íi]metro\s+(?:cef[áa]lico|abdominal|bra[çc]o)|"
                r"circunfer[êe]ncia\s+(?:abdominal|da\s+cintura|do\s+bra[çc]o))")
#: Escalas e classificações clínicas, com o nome ("Glasgow 13", "Child-Pugh C").
_ESCALA = (r"(?:Glasgow|Apgar|ECOG|MELD|Child-Pugh|PHQ-9|GAD-7|MEEM|Mini-?exame\s+do\s+Estado\s+Mental|Katz|Barthel|Lawton|"
           r"Rankin|Braden|Fugl-Meyer|Tinetti|EuroSCORE(?:\s+II)?|Kellgren-Lawrence|TI-RADS|BI-RADS|Bethesda|Gleason|"
           r"(?-i:CDR|ASIA|MRC|mMRC|FOIS|KDIGO|NYHA|SOFA|NIHSS|EDSS|CARS|SNAP-IV|M-CHAT|BPRS|ASA))")
#: Via de administração e frequência que acompanham a dose ("400 mg EV de 12/12 h", "50 mg pela manhã").
_VIA = (r"(?:(?-i:EV|IV|IM|VO|SC|SL)|endovenos[oa]|intravenos[oa]|intramuscular|subcut[âa]ne[oa]|via\s+oral|oral|inalat[óo]ri[oa]|"
        r"t[óo]pic[oa]|sublingual)")
_FREQUENCIA = (r"(?:(?:de\s+|a\s+cada\s+)?\d{1,2}\s*/\s*\d{1,2}\s*h(?:oras)?|a\s+cada\s+\d+\s+(?:horas|dias|semanas)|"
               r"(?:uma|duas|tr[êe]s|quatro|\d)\s+vez(?:es)?\s+(?:ao|por|na)\s+(?:dia|semana|m[êe]s)|\d\s*x\s*/?\s*(?:ao\s+)?dia|"
               r"ao\s+dia|por\s+dia|/dia|pela\s+manh[ãa]|[àa]\s+noite|[àa]\s+tarde|[àa]s\s+\d{1,2}\s*h|em\s+jejum|"
               r"antes\s+d[oa]s?\s+\w+|ap[óo]s\s+(?:[oa]s?\s+)?\w+|se\s+(?:dor|febre|necess[áa]rio)|em\s+dose\s+[úu]nica|"
               r"por\s+\d+\s+(?:dias|semanas|meses))")
_DOSE_POSOLOGIA = rf"{_NUM}\s*(?:mg|mcg|µg|UI|U|g|mL|ml|gotas|cp|comprimidos?|c[áa]psulas?|ampolas?|jatos?)(?:\s*/\s*(?:kg|mL|dia|dose|m²))?"

SAUDE_CLINICA = [
    # Analito com resultado: "creatinina de 1,6 mg/dL", "anti-HCV reagente", "PCR | 96 mg/L".
    Padrao("SAUDE", rf"\b{_ANALITO}(?:\s+(?:m[áa]xim[oa]|m[íi]nim[oa]|de\s+alta|de\s+admiss[ãa]o|inicial|final|basal|s[ée]ric[oa]))?"
                    rf"(?:\s+de\s+controle)?\s*(?:de|:|=|\||\t)?\s*{_RESULTADO}", 0.65, camada=SEMANTICA,
           nome=ORIGEM_CLINICA + "exame"),
    # Sinal vital ou medida: "PA de 80 x 40 mmHg", "Peso: 31 kg", "IMC 34,1 kg/m²", "SpO2 mínima 86%".
    Padrao("SAUDE", rf"\b{_SINAL_VITAL}(?:\s+(?:m[íi]nim[oa]|m[áa]xim[oa]|de\s+admiss[ãa]o|inicial|final|pr[ée]-gestacional)){{0,2}}"
                    rf"(?:\s+(?:no|na|em|ao)\s+\w+)?\s*(?:de|:|=|\||\t)?\s*{_NUM}(?:\s*(?:x|X|/|por)\s*{_NUM})?"
                    r"\s*(?:mmHg|bpm|irpm|ipm|%|°C|ºC|kg/m²|kg/m2|kg|g|cm|m|mg/dL)?(?!\w)", 0.65, camada=SEMANTICA,
           nome=ORIGEM_CLINICA + "sinal-vital"),
    # Peso da pessoa e sua variação: "pesando 16 kg", "perda de 7 kg em dois meses".
    Padrao("SAUDE", rf"\b(?:pes(?:o|ando|ava|ou)\s*(?:de|:)?\s*{_NUM}\s*kg|(?:perda|ganho|redu[çc][ãa]o)\s+(?:de\s+)?(?:peso\s+(?:de\s+)?)?"
                    rf"{_NUM}\s*kg(?:\s+em\s+\w+\s+(?:dias|semanas|meses|anos))?)\b", 0.65, camada=SEMANTICA,
           nome=ORIGEM_CLINICA + "peso"),
    # Escala clínica com pontuação, grau ou classe: "Glasgow 13", "ECOG 2", "Apgar 9/10", "Child-Pugh C".
    Padrao("SAUDE", rf"\b{_ESCALA}(?:\s+(?:de|da|do)\s+\w+)?\s*(?:de|:|=)?\s*"
                    r"(?:(?:grau|n[íi]vel|est[áa]gio|classe|escore|pontua[çc][ãa]o)\s+)?"
                    r"(?:\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?(?:\s*%|\s*pontos)?|(?-i:[A-E]|[IVX]{1,4})\b)(?:\s*\([^()\n]{1,40}\))?",
           0.65, camada=SEMANTICA, nome=ORIGEM_CLINICA + "escala"),
    # Dose com via ou frequência: "400 mg EV de 12/12 h", "20 UI antes do café", "0,5 mg à noite".
    Padrao("SAUDE", rf"\b{_DOSE_POSOLOGIA}(?:\s*,?\s*(?:{_VIA}|{_FREQUENCIA})){{1,4}}", 0.65, camada=SEMANTICA,
           nome=ORIGEM_CLINICA + "posologia"),
    # Fórmula obstétrica ("G4 P3 (3 partos vaginais) A0") e idade gestacional com contexto de gestação.
    Padrao("SAUDE", r"(?-i:\bG\s?\d{1,2}\s?P\s?\d{1,2}(?:\s*\([^()\n]{1,40}\))?\s?A\s?\d{1,2}\b)", 0.65, camada=SEMANTICA,
           nome=ORIGEM_CLINICA + "obstetricia"),
    Padrao("SAUDE", r"\b\d{1,2}\s+semanas(?:\s+e\s+\d\s+dias?)?(?:\s+de\s+(?:gesta[çc][ãa]o|gravidez|idade\s+gestacional))?",
           0.65, camada=SEMANTICA, contexto=(r"gesta[çc][ãa]o", "gestante", r"gr[áa]vida", r"pr[ée]-natal", "parto", "IG",
                                             r"obst[ée]tric[oa]"),
           contexto_obrigatorio=True, janela=60, nome=ORIGEM_CLINICA + "idade-gestacional"),
    # Funcionalidade e restrição laboral recomendada por junta médica.
    Padrao("SAUDE", r"\b(?:(?:in)?dependente\s+para\s+(?:o\s+|a\s+|as\s+|os\s+)?(?:banho|vestir-se|alimentar-se|alimenta[çc][ãa]o|"
                    r"higiene|locomo[çc][ãa]o|transfer[êe]ncias?|deambular|atividades\s+(?:b[áa]sicas|instrumentais|de\s+vida\s+di[áa]ria))"
                    r"(?:\s*,\s*[\w-]+(?:\s+[\w-]+){0,3}|\s+e\s+[\w-]+(?:\s+(?:d[oa]s?|de)\s+[\w-]+)?){0,6}|"
                    r"restri[çc][ãa]o\s+(?:ao|[àa]|para|de)\s+(?:porte\s+de\s+arma|esfor[çc]os?|carga|levantamento|atividades?|"
                    r"trabalho|contato|exposi[çc][ãa]o|plant[õo]es|turno)[^.;\n]{0,80}|"
                    r"readapta[çc][ãa]o(?:\s+(?:funcional|provis[óo]ria|definitiva))?)",
           0.65, camada=SEMANTICA, nome=ORIGEM_CLINICA + "funcionalidade"),
    # Achados do exame psíquico.
    Padrao("SAUDE", r"\b(?:humor\s+(?:deprimido|depressivo|eut[íi]mico|ansioso|irrit[áa]vel|expansivo|elevado|l[áa]bil|disf[óo]rico)|"
                    r"afeto\s+(?:hipomodulado|embotado|restrito|aplainado|l[áa]bil|incongruente|ansioso|hipermodulado)|"
                    r"discurso\s+(?:lentificado|acelerado|desorganizado|empobrecido|prolixo)|"
                    r"pensamento\s+(?:lentificado|acelerado|desorganizado|empobrecido|delirante|tangencial)|"
                    r"psicomotricidade\s+\w+|agita[çc][ãa]o\s+psicomotora|anedonia|abulia|hipom[íi]mi(?:a|c[oa])|"
                    r"alucina[çc](?:[ãa]o|[õo]es)(?:\s+(?:auditivas?|visuais?|t[áa]teis?|residua(?:l|is))){0,2}|"
                    r"del[íi]rios?(?:\s+(?:persecut[óo]rios?|de\s+\w+))?|idea[çc][ãa]o\s+(?:suicida|de\s+morte|homicida)|"
                    r"(?:auto|hetero)agressividade|autoles(?:[ãa]o|[õo]es)(?:\s+n[ãa]o\s+suicida)?|"
                    r"preju[íi]zo\s+(?:de|da)\s+(?:mem[óo]ria|concentra[çc][ãa]o|aten[çc][ãa]o)(?:\s+recente)?|"
                    r"desorienta[çc][ãa]o(?:\s+(?:no\s+tempo|temporal|espacial|no\s+espa[çc]o|e\s+no\s+espa[çc]o)){0,2}|"
                    r"confus[ãa]o\s+mental|isolamento\s+social)",
           0.65, camada=SEMANTICA, nome=ORIGEM_CLINICA + "exame-psiquico"),
    # Achados do exame físico, mobilidade e cuidados: "crepitação à mobilização", "deambula com auxílio de
    # andador", "transfere-se da cama para a cadeira", "curativo diário do coto".
    Padrao("SAUDE", r"\b(?:crepita[çc][ãa]o|geno\s+(?:varo|valgo)|derrame\s+articular|flex[ãa]o\s+limitada|"
                    r"amplitude\s+de\s+movimento|for[çc]a\s+muscular|aus[êe]ncia\s+de\s+(?:for[çc]a|sensibilidade|reflexos?|"
                    r"movimentos?|controle)|perda\s+de\s+sensibilidade|diminui[çc][ãa]o\s+da\s+sensibilidade|"
                    r"(?:n[ãa]o\s+)?deambula(?:[çc][ãa]o)?|marcha\s+\w+|transfere-se|n[ãa]o\s+consegue|"
                    r"n[ãa]o\s+controla\s+esf[íi]ncteres|contato\s+visual|atraso\s+(?:de|do|no)\s+(?:fala|desenvolvimento|"
                    r"linguagem)|n[óo]dulos?|caro[çc]os?|indolor|[úu]tero\s+\w+|curativos?|sondas?|andador|bengala|"
                    r"muletas?|colete\s+\w+|[óo]rteses?|pr[óo]teses?|palmilhas?|cateterismo\s+vesical|"
                    r"acolhimento\s+(?:diurno|noturno|integral)|grupo\s+(?:terap[êe]utico|de\s+preven[çc][ãa]o\s+de\s+"
                    r"reca[íi]da|de\s+apoio)|projeto\s+terap[êe]utico\s+singular|reca[íi]das?|lapsos?|"
                    r"(?:treino|treinamento|exerc[íi]cios|fortalecimento|alongamento|estimula[çc][ãa]o|manobras)\s+"
                    r"(?:muscular|funcional|aer[óo]bicos?|respirat[óo]ri[oa]s?|de\s+\w+|t[áa]til|posturais|orofaciais)|"
                    r"sess[õo]es\s+de\s+\w+|(?-i:HAS|DM|DM2|DPOC|ICC|IRC|DRC|AVC|AVE|IAM|TCE|ITU|IVAS|TEP|TVP|LRA|SDRA))\b",
           0.65, camada=SEMANTICA, nome=ORIGEM_CLINICA + "exame-fisico"),
]
# Campo de formulário clínico cujo valor é a condição registrada ("Natureza: fratura dos ossos nasais",
# "Tipo de violência: física", "Parte do corpo atingida: cabeça/face", "Evolução: incapacidade
# temporária", "Forma: 1 – pulmonar"). O valor vai até o fim da linha.
SAUDE_CLINICA.append(
    Padrao("SAUDE", r"^[ \t]*(?:\d{1,2}[.)]\s*)?(?:natureza(?:\s+da\s+les[ãa]o)?|partes?\s+do\s+corpo(?:\s+atingidas?)?|"
                    r"tipos?\s+de\s+viol[êe]ncia|meios?\s+de\s+agress[ãa]o|forma(?:\s+cl[íi]nica)?|agravos?\s+associados?|"
                    r"tipo\s+de\s+entrada|procedimentos?(?:\s+realizados?)?|evolu[çc][ãa]o|"
                    r"motivo(?:\s+d[ao]\s+(?:interna[çc][ãa]o|atendimento|encaminhamento|acolhimento|consulta))?|"
                    r"queixa(?:\s+principal)?|quadro\s+cl[íi]nico|hip[óo]tese\s+diagn[óo]stica|conduta|tratamento(?:\s+atual)?|"
                    r"medica[çc][ãa]o(?:\s+(?:atual|em\s+uso))?|medicamentos\s+em\s+uso|esquema|antecedentes|comorbidades|"
                    r"les[ãa]o|les[õo]es|classifica[çc][ãa]o\s+final|causas?(?:\s+d[oa]\s+[óo]bito|\s+b[áa]sicas?)?|"
                    r"situa[çc][ãa]o\s+(?:na\s+alta|vacinal|atual)|cuidados|reabilita[çc][ãa]o|linguagem(?:\s+\w+)?|"
                    r"sa[úu]de|condi[çc][õo]es\s+de\s+sa[úu]de(?:\s+\w+){0,3}|"
                    # Exame físico por aparelho ou região ("Marcha: claudicante", "Joelhos: crepitação")
                    r"marcha|deambula[çc][ãa]o|pele(?:\s+e\s+mucosas)?|mucosas|aparelho\s+\w+|ausculta(?:\s+\w+)?|"
                    r"extremidades|estado\s+geral|neurol[óo]gico|ps[íi]quico|" + _PARTE_DO_CORPO + r")"
                    r"\s*(?:\([^()\n]{1,30}\))?\s*:[ \t]*"
                    r"(?!(?:nenhum[a]?|n[ãa]o(?:\s+se\s+aplica)?|nega|ausente|sem\s+altera[çc][õo]es)\W*$)"
                    # Natureza da manifestação ou do procedimento, que não descreve condição de saúde.
                    r"(?!(?:den[úu]ncia|reclama[çc][ãa]o|solicita[çc][ãa]o|sugest[ãa]o|elogio|pedido|consulta|informa[çc][ãa]o|"
                    r"manifesta[çc][ãa]o|criminal|c[íi]vel|administrativ[oa]|judicial)\W*$)(\S[^\n]{1,200})$",
           0.65, camada=SEMANTICA, grupo=1, nome=ORIGEM_REGISTRO + "campo"))
# Exame identificado pelo nome ("Biomicroscopia do OE:", "eletroencefalograma de 20/01/2025",
# "Cultura de escarro"): a classe dos exames de imagem e de função pelo radical e pelo sufixo, mais os
# exames laboratoriais e microbiológicos.
_EXAME = (r"(?:(?:eletro|eco|hemo|audio|lipido|coagulo|proteino|mielo|espermo|antibio|cardiotoco|uro|angio|tomo|cintilo|"
          r"mamo|radio|ultrassono|histero|colangio|arterio|flebo|linfo|uretro|cisto|colpo|laringo|naso|endo|colono|"
          r"retossigmoido|bronco|artro|laparo|video|fundo|biomicro|oftalmo|dermato|capilaro|tono|espiro|imitancio|campi|"
          r"densito|polissono|oxi|capno|elasto|neuro|cranio|ressono|fluoro|videofluoro|ergo|termo)[a-zà-ú]*?"
          r"(?:grafia|scopia|grama|metria)s?|tomografia|resson[âa]ncia(?:\s+magn[ée]tica)?|ultrassom|(?-i:USG|ECG|EEG|ENMG|PEATE|BERA|RX)|"
          r"raios?[- ]x|radiografia|cultura\s+de\s+[\w-]+(?:\s+[\w-]+)?|sorologias?|baciloscopia|gota\s+espessa|bi[óo]psia|"
          r"pun[çc][ãa]o\s+(?:aspirativa|lombar|biópsia)|anatomopatol[óo]gico|histopatol[óo]gico|imuno-?histoqu[íi]mica|"
          r"genotipagem|cari[óo]tipo|teste\s+(?:r[áa]pido|do\s+(?:suor|pezinho|olhinho|orelhinha)|de\s+caminhada|ergom[ée]trico|"
          r"molecular|para\s+[\w-]+)|triagem\s+(?:neonatal|auditiva)|exames?\s+(?:f[íi]sico|ps[íi]quico|cl[íi]nico|neurol[óo]gico|"
          r"oftalmol[óo]gico|dermatol[óo]gico|complementares|laboratoriais|de\s+controle)|acuidade\s+visual|campo\s+visual)")
_EXAME_RE = re.compile(r"\b" + _EXAME + r"(?!\w)", re.IGNORECASE)
SAUDE_CLINICA.append(
    Padrao("SAUDE", r"\b" + _EXAME + r"(?!\w)", 0.65, camada=SEMANTICA, nome=ORIGEM_CLINICA + "exame-nome"))
# Termos clínicos pela forma: dor, dificuldade, alteração ou condição de uma parte do corpo ("dor à
# palpação do arco costal", "dificuldade para dormir") e termos com sufixo de sinal, procedimento ou
# afecção (-algia, -emia, -patia, -plegia, -megalia, -ectomia, -stomia, -plastia, -rrafia, -centese).
_NAO_CLINICOS_SUFIXO = (r"(?!(?:nostalgia|academia|academias|epidemia|epidemias|pandemia|pandemias|endemia|endemias|bo[êe]mia|"
                        r"blasf[êe]mia|alquimia|simpatia|empatia|antipatia|telepatia|homeopatia|naturopatia|anatomia|dicotomia|"
                        r"autonomia|economia|astronomia|agronomia|gastronomia|taxonomia|ergonomia)\b)")
SAUDE_CLINICA.append(
    Padrao("SAUDE", r"\b" + _NAO_CLINICOS_SUFIXO + r"[a-zà-ú]{3,}(?:algia|emia|patia|plegia|paresia|megalia|ectomia|stomia|"
                    r"tomia|plastia|pexia|rrafia|centese|fasia|lalia|fagia|pneia|cardia|[úu]ria)s?\b", 0.65, camada=SEMANTICA,
           nome=ORIGEM_REGISTRO + "sufixo"))

# --------------------------------------------------------------------------- Vínculo no nível do documento
# Num documento centrado numa pessoa identificada (laudo, prontuário, atestado, perícia, relatório
# social, avaliação de benefício, ficha de notificação individual), o dado de saúde se refere a essa
# pessoa: não depende de pronome ou papel na mesma frase. O documento é reconhecido pela forma — campos
# de identificação da pessoa ("Paciente:", "Periciando:", "Data de nascimento:", "Prontuário:"), fórmula
# de atestação ("Atesto, para os devidos fins, que a Sra. …") — e o gênero clínico ou pericial, pelo
# título e pelas seções do registro ("HISTÓRICO", "EXAME FÍSICO", "DIAGNÓSTICO", "CONDUTA"). Boletins,
# notas técnicas, editais e comunicados, que tratam de grupos, não têm campos de identificação de pessoa.

_ROTULO_TITULAR = (r"nome(?:\s+(?:completo|civil))?(?:\s+d[oa](?:\([ao]\))?\s+(?:paciente|periciand[oa]|periciad[oa]|usu[áa]ri[oa]|requerente|"
                   r"benefici[áa]ri[oa]|segurad[oa]|servidor[a]?|crian[çc]a|adolescente|acolhid[oa]|assistid[oa]|interessad[oa]|"
                   r"gestante|v[íi]tima|declarante|pessoa\s+atendida|pessoa\s+acolhida))?|paciente|periciand[oa]|periciad[oa]|"
                   r"examinad[oa]|requerente|benefici[áa]ri[oa]|usu[áa]ri[oa]|segurad[oa]|servidor[a]?|crian[çc]a|adolescente|"
                   r"acolhid[oa]|assistid[oa]|interessad[oa]|v[íi]tima|declarante|gestante|pu[ée]rpera|falecid[oa]|"
                   r"reeducand[oa]|apenad[oa]|custodiad[oa]|internad[oa]|autuad[oa]|manifestante|titular|respons[áa]vel(?:\s+familiar)?|"
                   r"indiciad[oa]|acusad[oa]|processad[oa]|sindicad[oa]|investigad[oa]|requerid[oa]|recorrente|"
                   r"reclamante|denunciante|solicitante")
_ROTULO_IDENTIFICACAO = (r"data\s+de\s+nascimento|nascimento|(?-i:DN)|idade|sexo|(?-i:CPF|RG|CNS|NIS|NB|SIAPE|MASP)|"
                         r"cart[ãa]o\s+(?:nacional\s+de\s+sa[úu]de|SUS|do\s+SUS)|prontu[áa]rio(?:\s+\w+)?|registro(?:\s+hospitalar)?|"
                         r"matr[íi]cula(?:\s+\w+)?|filia[çc][ãa]o|nome\s+da\s+m[ãa]e|m[ãa]e|naturalidade|estado\s+civil|ra[çc]a/cor|"
                         r"escolaridade|leito|genitor[a]?|iniciais|resid[êe]ncia|endere[çc]o(?:\s+\w+)?|telefone(?:\s+\w+)?")
#: Campo ou seção que identifica a pessoa de quem o documento trata.
_CAMPO_TITULAR = re.compile(r"(?:^|\s{2,}|\||\t)[ \t]*(?:\d{1,2}[.)]\s*)?(?:" + _ROTULO_TITULAR + r")(?:\([ao]s?\))?\s*(?:n[º°o.]\s*)?:"
                            r"|^[ \t]*(?:\d{1,2}[.)]\s*)?(?:identifica[çc][ãa]o(?:\s+d[oa]\s+(?:caso|paciente|usu[áa]ri[oa]|pessoa(?:\s+\w+)?|"
                            r"crian[çc]a|adolescente|periciand[oa]|requerente|servidor[a]?|segurad[oa]|benefici[áa]ri[oa]|acolhid[oa]))?|"
                            r"caso\s+[íi]ndice|dados\s+d[oa]\s+(?:paciente|pessoa\s+\w+|crian[çc]a|adolescente|usu[áa]ri[oa]|caso|"
                            r"periciand[oa]|requerente|segurad[oa]|acolhid[oa]))[ \t]*$",
                            re.IGNORECASE | re.MULTILINE)
_CAMPO_IDENTIFICACAO = re.compile(r"(?:^|\s{2,}|\||\t)[ \t]*(?:\d{1,2}[.)]\s*)?(?P<rotulo>" + _ROTULO_IDENTIFICACAO
                                  + r")\s*(?:n[º°o.]\s*)?:", re.IGNORECASE | re.MULTILINE)
#: Fórmula de atestação ou declaração sobre uma pessoa ("Atesto … que a Sra. Fulana", "que YURI …").
_ATESTACAO = re.compile(r"\b(?:atesto|declaro|certifico)\b[^.\n]{0,220}?\bque\s+(?:[oa]\s+)?(?:(?-i:Sr|Sra|Dr|Dra)\b|"
                        r"paciente|servidor|menor|crian[çc]a|(?-i:[A-ZÀ-Ú][a-zà-ú]+\s+[A-ZÀ-Ú]|[A-ZÀ-Ú]{3,}\s+[A-ZÀ-Ú]{2,}))",
                        re.IGNORECASE)
#: Título de documento clínico ou pericial.
_GENERO_CLINICO = re.compile(
    r"\b(?:laudo|atestado|prontu[áa]rio|sum[áa]rio\s+de\s+alta|resumo\s+de\s+(?:alta|interna[çc][ãa]o|prontu[áa]rio)|"
    r"relat[óo]rio\s+(?:m[ée]dico|cl[íi]nico|de\s+alta|multiprofissional|psicossocial|psicol[óo]gico|fonoaudiol[óo]gico|"
    r"fisioterap[êe]utico|de\s+fisioterapia|odontol[óo]gico|de\s+enfermagem|de\s+investiga[çc][ãa]o)|"
    r"parecer\s+(?:m[ée]dico|m[ée]dico-pericial|de\s+junta|da\s+junta)|junta\s+m[ée]dica|per[íi]cia\s+m[ée]dica|"
    r"ficha\s+de\s+(?:notifica[çc][ãa]o|investiga[çc][ãa]o)|receitu[áa]rio|receita\s+m[ée]dica|encaminhamento|"
    r"guia\s+de\s+refer[êe]ncia|contrarrefer[êe]ncia|avalia[çc][ãa]o\s+(?:m[ée]dica|biopsicossocial|da\s+defici[êe]ncia|"
    r"funcional|neuropsicol[óo]gica|psicol[óo]gica)|exame\s+de\s+corpo\s+de\s+delito|investiga[çc][ãa]o\s+de\s+[óo]bito|"
    r"ficha\s+(?:de\s+)?(?:atendimento|cl[íi]nica|ambulatorial)|boletim\s+de\s+atendimento|parecer\s+psicol[óo]gico|"
    r"evolu[çc][ãa]o\s+(?:m[ée]dica|de\s+enfermagem|cl[íi]nica|multiprofissional)|declara[çc][ãa]o\s+de\s+comparecimento|"
    r"(?:solicita[çc][ãa]o|requisi[çc][ãa]o)\s+de\s+(?:exames?|procedimento|medicamento|interna[çc][ãa]o)|"
    r"relat[óo]rio\s+(?:nutricional|terap[êe]utico|de\s+terapia\s+ocupacional|neuropsicol[óo]gico|psiqui[áa]trico))\b",
    re.IGNORECASE)
#: Seção do registro clínico, em linha própria ou como rótulo.
_SECAO_CLINICA = re.compile(
    r"^[ \t]*(?:\d{1,2}[.)]\s*|[IVX]{1,4}\s*[–-]\s*)?(?:hist[óo]ric[oa](?:\s+cl[íi]nic[oa])?|hist[óo]ria(?:\s+(?:cl[íi]nica|da\s+doen[çc]a"
    r"(?:\s+atual)?|reprodutiva(?:\s+e\s+pr[ée]-natal)?))?|anamnese|exames?(?:\s+(?:f[íi]sico|ps[íi]quico|cl[íi]nico|complementares|"
    r"relevantes|laboratoriais))?|diagn[óo]sticos?(?:\s+\w+){0,2}|hip[óo]tese\s+diagn[óo]stica|evolu[çc][ãa]o|conduta|"
    r"prescri[çc][ãa]o(?:\s+\w+){0,2}|tratamento(?:\s+\w+)?|medica[çc][ãa]o(?:\s+\w+)?|medicamentos\s+em\s+uso|antecedentes|"
    r"comorbidades|quadro\s+cl[íi]nico|queixa(?:\s+principal)?|condi[çc][õo]es\s+de\s+sa[úu]de(?:\s+\w+){0,3}|dados\s+cl[íi]nicos"
    r"(?:\s+e\s+laboratoriais)?|les[ãa]o|les[õo]es|procedimentos?(?:\s+\w+)?|interna[çc][ãa]o|alergias|reabilita[çc][ãa]o|"
    r"situa[çc][ãa]o\s+vacinal|sa[úu]de|sinais\s+vitais|impress[ãa]o\s+diagn[óo]stica|progn[óo]stico|intercorr[êe]ncias|"
    r"plano\s+terap[êe]utico|exame\s+do\s+estado\s+mental)\s*(?::|$)", re.IGNORECASE | re.MULTILINE)
#: Licença, afastamento ou tratamento que enuncia o motivo de saúde.
_MOTIVO_DE_LICENCA = re.compile(r"\b(?:licen[çc]a|afastamento|tratamento\s+d[ae]\s+(?:pr[óo]pria\s+)?sa[úu]de|"
                                r"motivo\s+de\s+(?:doen[çc]a|sa[úu]de))", re.IGNORECASE)
#: Linha de título: sem minúsculas, com ao menos duas palavras e sem ponto final no meio.
_TITULO = re.compile(r"^[ \t]*(?:\d{1,2}[.)]\s*|[IVX]{1,4}\s*[–-]\s*)?(?=[^\n]*[A-ZÀ-Ú]{5}|[^\n]*[A-ZÀ-Ú]{3}[^\n]*\s[^\n]*"
                     r"[A-ZÀ-Ú]{3})[^a-zà-ÿ\n.:?]{5,90}$", re.MULTILINE)

#: Instituição, programa ou norma citados pelo nome próprio ("Hospital Universitário", "Programa de
#: Atenção …", "Política Nacional de Saúde Bucal", "Consultório na Rua"): o termo de saúde que integra o
#: nome não é dado de uma pessoa. As palavras seguintes começam por maiúscula, salvo os conectivos.
_CABECA_INSTITUICAO = (r"Hospital|Policl[íi]nica|Cl[íi]nica|Centro|Unidade|Servi[çc]o|Consult[óo]rio|Ambulat[óo]rio|Instituto|"
                       r"Laborat[óo]rio|Departamento|Divis[ãa]o|N[úu]cleo|Coordena[çc][ãa]o|Coordenadoria|Ger[êe]ncia|"
                       r"Superintend[êe]ncia|Diretoria|Secretaria|Subsecretaria|Minist[ée]rio|Programa|Pol[íi]tica|Plano|Rede|"
                       r"Sistema|Subsistema|Junta|Comiss[ãa]o|Comit[êe]|Conselho|Funda[çc][ãa]o|Associa[çc][ãa]o|Casa|Lar|Escola|"
                       r"Universidade|Faculdade|Vara|Juizado|Tribunal|Defensoria|Promotoria|Procuradoria|Delegacia|Pol[íi]cia|"
                       r"Guia|Protocolo|Diretrizes|Estatuto|C[óo]digo|Classifica[çc][ãa]o|Distrito|Ag[êe]ncia|Campanha|"
                       r"Calend[áa]rio|Pr[êe]mio|Fundo|Terra|Reserva|Territ[óo]rio|Maternidade|Pronto-Socorro|Estrat[ée]gia|"
                       r"Benef[íi]cio|Cadastro|Componente|Subse[çc][ãa]o|Se[çc][ãa]o|Central|Lei|Constitui[çc][ãa]o|Opera[çc][ãa]o|"
                       r"Terminal|Tratamento\s+Fora")
#: Palavra de nome próprio: inicial maiúscula, sigla ou ordinal ("10ª"); sigla de documento pessoal não.
_PALAVRA_NOME = (r"(?!(?:CPF|RG|CNS|NIS|NB|PIS|CNH|CTPS|SIAPE|MASP|OAB|CRM)\b)(?:[A-Z]{2,}[\w/-]*|[A-ZÀ-Ú][\w-]*|"
                 r"\d+[ªº°])")
_CONECTIVO_NOME = r"(?:d[aoe]s?|e|em|para|por|na|no|nas|nos|[àa]|ao|aos|[àa]s|contra|sobre|com|–|-)"
_NOME_INSTITUICAO = re.compile(r"(?-i:\b(?:" + _CABECA_INSTITUICAO + r"|" + _CABECA_INSTITUICAO.upper() + r"))(?:[ \t]+(?:"
                               + _CONECTIVO_NOME + r"[ \t]+)?(?-i:" + _PALAVRA_NOME + r"))+", re.IGNORECASE)
#: Programa, estratégia ou campanha com nome próprio após o substantivo comum ("estratégia Zero Morte
#: Materna", "programa Bolsa Família").
_NOME_PROGRAMA = re.compile(r"\b(?:estrat[ée]gia|programa|projeto|campanha|plano|pol[íi]tica|rede|sistema|protocolo|"
                            r"diretrizes|guia)[ \t]+(?-i:[A-ZÀ-Ú][\w-]*)(?:[ \t]+(?:" + _CONECTIVO_NOME
                            + r"[ \t]+)?(?-i:" + _PALAVRA_NOME + r"))*", re.IGNORECASE)
#: Sequência de palavras com inicial maiúscula no meio da frase, ou sigla seguida delas ("Terminal
#: Rodoviário de Ribeirão Preto", "SISVAN Indígena"): nome próprio que a extensão do trecho de saúde não
#: atravessa. Não isenta o termo, que pode ser o próprio nome da doença ("Síndrome de Down").
_NOME_PROPRIO = re.compile(r"(?<=[a-zà-ú,;)]\s|\b(?:d[aoe]s?|n[oa]s?|ao|aos|à|às|pel[oa]s?|para|em)\s)(?-i:[A-ZÀ-Ú][\w-]+|[A-Z]{2,})"
                           r"(?:[ \t]+(?:" + _CONECTIVO_NOME + r"[ \t]+)?(?-i:[A-ZÀ-Ú][\w-]+|[A-Z]{2,}))+")
#: Serviço designado pela especialidade ("ambulatório de pé diabético", "enfermaria de clínica cirúrgica",
#: "leitos de UTI"): nomeia o serviço, não a condição da pessoa.
_SERVICO_COMUM = re.compile(r"\b(?:ambulat[óo]rios?|enfermarias?|setor|leitos?|unidades?\s+de\s+(?:terapia|interna[çc][ãa]o|"
                            r"cuidados)|servi[çc]os?\s+de\s+(?:refer[êe]ncia|aten[çc][ãa]o))\s+(?:de|da|do)\s+[\wà-ú-]+"
                            r"(?:\s+(?:de|da|do|e)\s+[\wà-ú-]+)?(?:\s+(?:intensiva|adulto|pedi[áa]trica|neonatal))?"
                            # Nome legal do benefício ("benefício assistencial à pessoa com deficiência").
                            r"|\bbenef[íi]cios?\s+(?:assistencia(?:l|is)|de\s+presta[çc][ãa]o\s+continuada)\s+(?:[àa]|ao)\s+"
                            r"(?:pessoa\s+(?:com\s+defici[êe]ncia|idosa|portadora\s+de\s+defici[êe]ncia)|idoso)",
                            re.IGNORECASE)
_SERVICO_SAUDE_MENTAL_RE = re.compile(_SERVICO_SAUDE_MENTAL, re.IGNORECASE)
#: Siglas de serviços de saúde e assistência ("CAPS AD", "UBS", "CER II").
_SIGLA_SERVICO = re.compile(r"(?-i:\b(?:CAPS(?:\s*(?:AD|i|ij|IJ|II|III|AD\s+III))?|CAPSi|UBSF?|UPA|USF|ESF|CER(?:\s+[IV]+)?|CREAS|CRAS|"
                            r"SAMU|SAME|SIASS|LACEN(?:/\w+)?|CIEVS(?:-\w+)?|SINAN|INSS|NASF|CEO|SAE|CTA|IML|CTA)\b)")
#: Referência a norma: "Lei nº 8.112/1990", "art. 202 da Lei …", "RDC ANVISA nº 502/2021".
_NORMA = re.compile(r"\b(?:arts?\.\s*\d+[º°]?(?:[-–]?[A-Z])?(?:\s*,\s*(?:§|inc(?:iso)?\.?|al[íi]nea|caput|par[áa]grafo)[^,;.)\n]{0,20})*"
                    r"(?:\s*,?\s+d[aoe]s?\s+(?=\w))?|(?:Lei(?:\s+Complementar|\s+Federal|\s+Estadual|\s+Municipal)?|Decreto(?:-Lei)?|"
                    r"Portaria(?:\s+de\s+Consolida[çc][ãa]o)?|Resolu[çc][ãa]o|(?-i:RDC)|Instru[çc][ãa]o\s+Normativa|Medida\s+Provis[óo]ria|"
                    r"Emenda\s+Constitucional|Nota\s+T[ée]cnica)(?:\s+[A-Z][\w/-]*){0,3}\s+n[º°o.]?\s*[\d./-]+\d(?:,\s+de\s+\d{1,2}\s+de\s+\w+"
                    r"\s+de\s+\d{4})?)", re.IGNORECASE)
#: Conectivos que introduzem fundamento normativo ou critério; a extensão do trecho de saúde para neles.
_CONECTIVO_NORMATIVO = re.compile(r"\b(?:conforme|nos\s+termos\s+d[aoe]s?|de\s+acordo\s+com|segundo\s+(?:[oa]s?\s+)?(?=[A-Z])|"
                                  r"previst[oa]s?\s+n[oa]s?|especificad[oa]s?\s+n[oa]s?|definid[oa]s?\s+n[oa]s?|"
                                  r"com\s+fundamento\s+n[oa]s?|para\s+fins\s+d[eo])\b")
#: Negação ou hipótese: "nega alergias", "sem sintomas psicóticos", "Não foram observados sinais de…",
#: "procurar emergência em caso de febre".
_NEGACAO_ANTES = re.compile(r"\b(?:nega(?:m|va|ndo)?|negou|sem|aus[êe]ncia\s+de|em\s+caso\s+de|na\s+presen[çc]a\s+de|"
                            r"se\s+houver|n[ãa]o\s+(?:apresenta(?:va)?|h[áa]|houve|possui|"
                            r"tem|refere|foram\s+(?:observad|identificad|constatad|encontrad)[oa]s|foi\s+(?:observad|identificad|"
                            r"constatad|encontrad)[oa]|se\s+observ\w+)(?:\s+(?:sinais|ind[íi]cios|evid[êe]ncias|hist[óo]rico|"
                            r"qualquer|nenhum[a]?|outr[oa]s?)(?:\s+de)?)?)\s+(?:\w+\s+){0,2}$", re.IGNORECASE)
#: Pergunta ou campo de formulário respondido com "não" ("Possui deficiência? não", "Gestante: 5 – não").
_NEGACAO_DEPOIS = re.compile(r"[^\n?:]{0,30}[?:]\s*(?:\d\s*[–-]\s*)?n[ãa]o\b", re.IGNORECASE)
#: Rótulo de campo: o termo seguido de dois-pontos ("Internação: 03/06/2025", "Nome social: …"), no início da
#: linha ou depois de numeração e marcador de opção ("2.", "[X]").
_ROTULO_DEPOIS = re.compile(r"\s*(?:\([^()\n]{0,20}\)\s*)?:")
_ANTES_DO_ROTULO = re.compile(r"[ \t\d.)•–-]*(?:\[[ xX]?\]|\([ xX]?\))?[ \t]*")
#: Fronteiras do trecho estendido: quebra de linha (exceto a continuação recuada de uma prescrição),
#: separador de campos ou de células, ponto e vírgula, ponto de interrogação ou exclamação e ponto final
#: que não abrevia ("Dr.", "nº.", "P. falciparum") nem separa decimais.
_FRONTEIRA = re.compile(r"\n(?![ \t]{2,}\S)|(?<=\S)[ \t]{3,}|\t|\s\|\s?|\|\s|;|[?!]|(?<![\s(][A-Za-z]|\b(?:Dr|Dra|Sr|Sra|Prof|Profa|"
                        r"art|arts|n[º°o]|fls?|inc|al|p|pp|cap|ex|aprox|cf|obs|tel|vol|ed)|\.)\.(?=\s|$)")
_MESES = r"(?:janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
#: Atributo que integra a expressão da condição (convenção de extensão das diretrizes de anotação):
#: tempo ("há 14 anos", "desde 2021", "em 12/03/2025"), estado do tratamento (", em tratamento desde…",
#: ", com tratamento interrompido…"), frequência ("três vezes por semana") e causa ("em razão de
#: paralisia cerebral").
_ATRIBUTO = re.compile(
    r",?\s+(?:desde|h[áa])\s+(?:\+\s+de\s+|mais\s+de\s+|cerca\s+de\s+|umas?\s+|uns\s+|quase\s+)?(?:\d{4}|\d+\s+(?:anos?|meses|dias|semanas)|"
    rf"{_MESES}(?:\s+de\s+\d{{4}})?|{_EXTENSO}\s+"
    r"(?:anos?|meses|dias|semanas)|a\s+(?:adolesc[êe]ncia|inf[âa]ncia|juventude|pris[ãa]o|interna[çc][ãa]o|gesta[çc][ãa]o)|"
    r"o\s+(?:ingresso|nascimento|diagn[óo]stico|parto)|"
    # Idade de início ("desde os 13 anos", "desde os dezenove") e duração sem número ("há semanas").
    rf"os\s+(?:\d{{1,2}}|{_EXTENSO})(?:\s+anos)?|anos|meses|semanas|dias)"
    # Oração temporal com verbo no passado ("desde que perdeu o emprego", "desde que se aposentou").
    r"|,?\s+desde\s+que\s+(?:se\s+)?\w+(?:ou|eu|iu|ram)\b[^.;,\n()]{0,40}"
    r"|\s+dos\s+\d{1,2}\s+aos\s+\d{1,2}\s+anos"
    rf"|,?\s+em\s+(?:\d{{1,2}}/\d{{1,2}}/\d{{2,4}}|\d{{4}}|{_MESES}(?:\s+de\s+\d{{4}})?)"
    r"|,?\s+(?:em|com|sem)\s+(?:tratamento|acompanhamento|terapia|abstin[êe]ncia|remiss[ãa]o|cirurgia|uso\s+de|"
    r"(?-i:TARV|PQT|TDO|PrEP))\b[^.;,\n()]{0,50}"
    # Estado do tratamento ou da lesão em particípio ("corte suturado", ", interrompido desde a prisão",
    # ", aguardando cirurgia").
    r"|,?\s+(?:suturad|infectad|cicatrizad|interrompid|suspens|abandonad|retomad|conclu[íi]d|controlad|compensad|"
    r"descompensad|operad|tratad)[oa]s?(?:\s+(?:desde|h[áa]|em|aos?)\s+[^.;,\n()]{1,40})?"
    r"|,?\s+aguardando\s+(?:cirurgia|transplante|consulta|tratamento|vaga|exame|avalia[çc][ãa]o|pr[óo]tese)\b"
    r"|\s+(?:(?:uma|duas|tr[êe]s|quatro|cinco|\d)\s+vez(?:es)?\s+(?:por|ao|na)\s+(?:dia|semana|m[êe]s)|di[áa]ri[oa]|semanal|mensal)"
    # Frequência e período ("todos os dias", "nos fins de semana", "de manhã e à noite", "de madrugada").
    r"|\s+(?:todos\s+os\s+dias|todo\s+dia|diariamente|(?:nos|aos)\s+fins\s+de\s+semana|de\s+madrugada|"
    r"(?:de\s+manh[ãa]|pela\s+manh[ãa])(?:\s+e\s+[àa]\s+noite)?|[àa]\s+noite|ao\s+deitar|"
    r"(?:a\s+cada|de)\s+(?:\d{1,2}|quinze|sete|trinta)\s+dias|quinzena(?:l|lmente)|semanalmente|"
    r"no\s+(?:turno|per[íi]odo)\s+(?:da\s+(?:manh[ãa]|tarde|noite)|matutino|vespertino|noturno))"
    r"|\s+(?:em\s+raz[ãa]o\s+d[eoa]|em\s+decorr[êe]ncia\s+d[eoa]|decorrente\s+de|secund[áa]ri[oa]\s+a)\s+[^.;,\n()]{3,60}"
    r"|,?\s+sem\s+(?:les[õo]es|altera[çc][õo]es|sinais|curativo|medica[çc][ãa]o|tratamento|acompanhamento|"
    r"retirar\s+a\s+medica[çc][ãa]o)\b[^.;,\n()]{0,40}"
    r"|\s+com\s+(?:implante|coloca[çc][ãa]o)\s+de\s+[^.;,\n()]{2,40}",
    re.IGNORECASE)
#: Pontuação e palavras funcionais (artigos, preposições e conjunções) que não começam nem terminam o
#: trecho estendido.
_BORDA_FRACA = re.compile(r"^(?:[\s,.:;–—\-()\"“”']|(?:e|ou|o|a|os|as|de|do|da|dos|das|em|no|na|nos|nas|ao|aos|à|às|pelo|"
                          r"pela|pelos|pelas|para|com|por|que|um|uma)\b)+", re.IGNORECASE)
_BORDA_FRACA_FIM = re.compile(r"(?:[\s,.:;–—\-(\"“”']|\b(?:e|ou|o|a|os|as|de|do|da|dos|das|em|no|na|nos|nas|ao|aos|à|às|pelo|"
                              r"pela|pelos|pelas|para|com|por|que|um|uma)\b)+$", re.IGNORECASE)
#: Motivos de :meth:`ContextoDocumental.isencao`; o termo isento não é tarjado por coerência com outra
#: ocorrência tarjada (ver :meth:`themis_lgpd.motor.Anonimizador._saude_consistente`).
ISENCAO_NOME = "Termo em nome de instituição, programa ou norma"
ISENCAO_NEGACAO = "Termo negado, hipotético ou campo respondido com \"não\""
ISENCAO_TITULO = "Termo em título do documento"
ISENCAO_ROTULO = "Rótulo de campo"
ISENCAO_ASSINATURA = "Especialidade na linha de assinatura do profissional"
ISENCAO_CLASSIFICACAO = "Classificação do caso no cabeçalho (classe, assunto, natureza)"
ISENCAO_SIGLA = "Trecho em maiúsculas sem termo de saúde reconhecido"
ISENCAO_PERGUNTA = "Termo em pergunta ou quesito de formulário"
ISENCAO_AGREGADO = "Termo em contagem ou estatística de um grupo"
ISENCAO_FRAGMENTO = "Trecho do classificador sem termo de saúde (início em palavra funcional, medida ou material de obra)"
ISENCAO_SOCIOEDUCATIVA = "Internação como medida socioeducativa"
MOTIVOS_ISENCAO = frozenset({ISENCAO_NOME, ISENCAO_NEGACAO, ISENCAO_TITULO, ISENCAO_ROTULO, ISENCAO_ASSINATURA,
                             ISENCAO_CLASSIFICACAO, ISENCAO_SIGLA, ISENCAO_PERGUNTA, ISENCAO_AGREGADO, ISENCAO_FRAGMENTO,
                             ISENCAO_SOCIOEDUCATIVA})
#: Quantidade em algarismos (com separador de milhar ou decimal) ou por extenso.
_NUMERAL = (rf"(?:(?<![\w.,/])\d{{1,3}}(?:\.\d{{3}})+(?:,\d+)?|(?<![\w.,/])\d+(?:,\d+)?|\b(?:{_EXTENSO}|cem|cento|mil|duzent[oa]s|"
            r"trezent[oa]s|quinhent[oa]s))")
#: Quantidade de dez ou mais: contagem menor de pessoas pode ser a de uma família ("tenho duas crianças com
#: autismo").
_NUMERAL_GRUPO = (r"(?:(?<![\w.,/])(?:\d{1,3}(?:\.\d{3})+|[1-9]\d+)(?:,\d+)?|\b(?:dez|onze|doze|treze|quatorze|catorze|quinze|"
                  r"dezesseis|dezessete|dezoito|dezenove|vinte|trinta|quarenta|cinquenta|cem|cento|mil|duzent[oa]s|trezent[oa]s|"
                  r"quinhent[oa]s))")
#: Evento contado ("52 notificações de", "41 casos de"); como no grupo de pessoas, a contagem menor que dez
#: pode ser o histórico de uma pessoa ou família ("tivemos 2 casos de covid em casa").
_EVENTOS = r"(?:casos|notifica[çc][õo]es|registros|ocorr[êe]ncias|den[úu]ncias|pedidos|encaminhamentos|[óo]bitos|boletins)"
#: Grupo de pessoas contado ("418 mulheres", "38 estudantes").
_POPULACAO = (r"(?:pessoas|mulheres|homens|crian[çc]as|adolescentes|jovens|idos[oa]s|estudantes|alun[oa]s|pacientes|"
              r"usu[áa]ri[oa]s|gestantes|lactantes|pu[ée]rperas|fam[íi]lias|v[íi]timas|servidor(?:es|as)|benefici[áa]ri[oa]s|"
              r"moradores|ind[íi]genas|detent[oa]s|intern[oa]s|pres[oa]s|apenad[oa]s|custodiad[oa]s|socioeducand[oa]s|acolhid[oa]s|"
              r"habitantes|trabalhador(?:es|as)|candidat[oa]s|inscrit[oa]s|matr[íi]culas|vagas|leitos|munic[íi]pios|escolas|unidades)")
#: Contagem de um grupo logo antes do termo: "41 casos de", "38 estudantes com", "63% em", "nove deles com",
#: "236 com" (lista de contagens). As palavras são separadas por espaço ou tabulação, sem atravessar a frase.
_AGREGADO_ANTES = re.compile(
    _NUMERAL + r"[ \t]*(?:%|por[ \t]+cento)[ \t]+(?:d[oa]s[ \t]+[\wà-ú-]+[ \t]+)?(?:em|com|de|eram|tinham|apresentavam|sofreram)[ \t]+$"
    r"|" + _NUMERAL_GRUPO + r"[ \t]+(?:" + _EVENTOS + r"|" + _POPULACAO + r")"
    r"(?:[ \t]+[\wà-ú-]+){0,2}?[ \t]+(?:com|de|por|em|sem|contra|a)[ \t]+"
    r"(?:situa[çc][ãa]o[ \t]+de[ \t]+)?(?:[\wà-ú-]+(?:[ \t]+[\wà-ú-]+){0,2}[ \t]+(?:e|ou)[ \t]+)?$"
    r"|" + _NUMERAL + r"[ \t]+(?:deles|delas|dos[ \t]+quais|das[ \t]+quais|destes|destas|desses|dessas)[ \t]+"
    r"(?:(?:com|em|eram|s[ãa]o|tinham|apresentavam)[ \t]+)?$",
    re.IGNORECASE | re.REVERSE)
#: Contagem de ao menos dez imediatamente antes do termo no plural ou de "com" ("12 gestantes", "6.214
#: internações", "236 com transtorno …"); contagens menores podem ser o histórico de uma pessoa ("duas
#: internações", "3 cirurgias"), e o ano ou a data que precede o termo não é contagem.
_CONTAGEM_ANTES = re.compile(r"(?<![\w.,/])(?!(?:19|20)\d\d\b)(?:\d{1,3}(?:\.\d{3})+|[1-9]\d+)[ \t]+(?P<com>com[ \t]+)?$",
                             re.REVERSE)
#: Núcleos genéricos de saúde, que não identificam a condição sem o qualificador ("deficiência" diante de
#: "deficiência auditiva").
_NUCLEOS_GENERICOS = frozenset({
    "deficiencia", "deficiencias", "doenca", "doencas", "transtorno", "transtornos", "sindrome", "cirurgia", "cirurgias",
    "tratamento", "internacao", "internacoes", "dor", "dores", "lesao", "lesoes", "problema", "problemas", "condicao",
    "crise", "crises", "infeccao", "cancer", "vacina", "vacinacao", "exame", "exames", "consulta", "consultas",
    "acompanhamento", "uso", "gestacao", "gestante", "febre", "alergia",
})


def termo_generico(chave: str) -> bool:
    """Indica se o termo (sem acentos, em minúsculas) é núcleo genérico de :data:`_NUCLEOS_GENERICOS`."""
    return chave in _NUCLEOS_GENERICOS


#: Indícios de contagem que precedem as expressões de :data:`_AGREGADO_ANTES`, verificados antes dela.
_INDICIOS_DE_CONTAGEM = ("deles", "delas", "quais", "destes", "destas", "desses", "dessas", "casos", "notifica", "registros",
                         "ocorr", "denúncias", "denuncias", "pedidos", "encaminhamentos", "atendimentos", "óbitos", "obitos",
                         "boletins")


def agregado(texto: str, ini: int, fim: int) -> bool:
    """Indica se o termo sensível integra a contagem de um grupo ("41 casos de violência sexual", "seis
    delas gestantes", "63% em situação de violência"), e não a descrição de uma pessoa."""
    antes = texto[max(0, ini - 120):ini]
    if not any(c.isdigit() for c in antes):
        minusculo = antes.lower()
        if not any(p in minusculo for p in _INDICIOS_DE_CONTAGEM):
            return False
    if _AGREGADO_ANTES.search(antes):
        return True
    m = _CONTAGEM_ANTES.search(antes)
    return m is not None and (m.group("com") is not None or _PLURAL.match(texto, ini, fim) is not None)


#: Conjunção ou artigo estrangeiro no início de trecho do classificador: borda mal posta ("e que perdeu",
#: "al médico").
_FUNCIONAL_INICIAL = re.compile(r"(?:e\s+que|que|al|el|la|lo|y)\b", re.IGNORECASE)
#: Medida técnica e material de obra que o classificador confunde com achado clínico ("fck 35 MPa", "pedra
#: tosca rejuntada").
_MEDIDA_DE_OBRA = re.compile(r"\b(?:\d+(?:[.,]\d+)?\s*)?(?-i:MPa|GPa|kPa|kN|kgf|tf)\b|\bfck\b|\b(?:pedras?|concreto|asfalto|brita|"
                             r"areia|cimento|argamassa|tijolos?|blocos?|lajes?|vigas?|pilares?|pavimenta[çc][ãa]o|cal[çc]amento|"
                             r"rejuntad[oa]s?|drenagem|terraplenagem|meio-fio|sarjetas?)\b", re.IGNORECASE)
#: "Internação" sem qualificador, que em documento socioeducativo designa a medida do ECA (arts. 121 a
#: 125), salvo com menção a serviço de saúde na mesma frase.
_INTERNACAO_SIMPLES = re.compile(r"interna(?:[çc](?:[ãa]o|[õo]es)|d[oa]s?)", re.IGNORECASE)
_SOCIOEDUCATIVO = re.compile(r"\b(?:socioeducativ[oa]s?|socioeducand[oa]s?|ato\s+infracional|semiliberdade|"
                             r"interna[çc][ãa]o\s+provis[óo]ria|unidades?\s+de\s+interna[çc][ãa]o|medida\s+de\s+interna[çc][ãa]o)\b",
                             re.IGNORECASE)
_SERVICO_HOSPITALAR = re.compile(r"\b(?:hospita\w*|(?-i:UTI|UPA)|cl[íi]nicas?|enfermarias?|leitos?|alta|m[ée]dic\w*|psiqui\w*|"
                                 r"maternidade|pronto-socorro|pronto-atendimento|comunidades?\s+terap[êe]uticas?|cir[úu]rgi\w*)\b",
                                 re.IGNORECASE)
_FIM_DE_FRASE = re.compile(r"[.!?;](?=\s|$)|\n")
_MEDICAMENTO_OU_DISPOSITIVO = re.compile(r"(?:insulinas?|bombinhas?|nebuliza\w+|inaladores?|[óo]rteses?|pr[óo]teses?|"
                                         r"cadeiras?\s+de\s+rodas|fraldas?|sondas?|medica[çc](?:[ãa]o|[õo]es)|rem[ée]dios?|"
                                         r"aparelhos?\s+auditivos?|glicos[íi]metros?|muletas?|andador)\b", re.IGNORECASE)
#: Vocabulário de estatística e de indicador.
_ESTATISTICA = re.compile(r"\b(?:em\s+m[ée]dia|m[ée]dia\s+de|mediana|taxa\s+de|percentua(?:l|is)|propor[çc][ãa]o|"
                          r"incid[êe]ncia|preval[êe]ncia|indicador(?:es)?)\b", re.IGNORECASE)


def _limites_da_frase(texto: str, ini: int, fim: int) -> tuple[int, int]:
    """Início e fim da frase (ou da linha) que contém o trecho, até 300 caracteres de cada lado."""
    a = max((m.end() for m in _FIM_DE_FRASE.finditer(texto, max(0, ini - 300), ini)), default=max(0, ini - 300))
    m = _FIM_DE_FRASE.search(texto, fim, min(len(texto), fim + 300))
    return a, m.start() if m else min(len(texto), fim + 300)


def _servico_nomeado(texto: str, ini: int, fim: int) -> bool:
    """Indica se o serviço de saúde mental em ``texto[ini:fim]`` é citado pelo nome da unidade: palavra de
    inicial maiúscula além das siglas de modalidade ou do nome por extenso do serviço, ou nome próprio logo
    depois ("CAPS Infantojuvenil", "CAPS III Leste", "Centro de Atenção Psicossocial de Teresina")."""
    if re.match(r"(?-i:Centro\s+de\s+Aten)", texto[ini:fim]):
        return True
    if re.search(r"(?-i:\b(?!CAPS|AD|II|III|IJ|CAPSi|CAPSij)[A-ZÀ-Ú][\wà-ú]+)", texto[ini:fim]):
        return True
    return bool(re.match(r"\s+(?:(?:de|do|da)\s+)?(?-i:[A-ZÀ-Ú][\wà-ú]+)", texto[fim:fim + 40]))
#: Campo de cabeçalho com a classificação processual ou policial do caso ("Classe – Assunto: Medidas
#: Protetivas de Urgência – Violência Doméstica", "Título: Injúria racial (art. …)"): tipifica o caso, não
#: descreve a pessoa.
_CAMPO_CLASSIFICACAO = re.compile(r"[ \t]*(?:classe(?:\s*[–-]\s*assunto)?|assunto|natureza|t[íi]tulo|tipifica[çc][ãa]o|"
                                  r"incid[êe]ncia\s+penal)\s*:", re.IGNORECASE)
#: Palavra com inicial maiúscula ou sigla imediatamente antes do termo.
_NOME_ANTES = re.compile(r"(?-i:\b(?:[A-ZÀ-Ú][\w-]*|[A-Z]{2,}))[ \t]+$")
#: Termo de várias palavras com inicial maiúscula (salvo os conectivos) e palavra com inicial maiúscula,
#: seguida ou não de conectivo, logo antes dele.
_TITULO_PROPRIO = re.compile(r"(?-i:[A-ZÀ-Ú][a-zà-ú][\wà-ú-]*(?:[ \t]+(?:(?:d[aoe]s?|em|a|à|e|para|com|contra)[ \t]+)?"
                             r"[A-ZÀ-Ú][a-zà-ú][\wà-ú-]*)+)")
_CONTINUA_NOME = re.compile(r"(?:(?-i:\b[A-ZÀ-Ú][a-zà-ú][\wà-ú-]*)[ \t]+(?:(?:d[aoe]s?|em|a|à|e|para|com|contra)[ \t]+)?){2,}$",
                            re.REVERSE)
#: Núcleo de nome de unidade, programa ou cargo na sequência que o termo continua: sem ele, a sequência de
#: iniciais maiúsculas pode ser só a grafia do pedido ("Sofro De Fibromialgia").
_CABECA_DE_NOME = re.compile(r"(?-i:\b(?:" + _CABECA_INSTITUICAO + r"|Diretora?|Coordenadora?|Gerente|Chefe|Secret[áa]ri[oa]|"
                             r"Superintendente|Aten[çc][ãa]o|Vigil[âa]ncia|Prote[çc][ãa]o|Apoio|Enfrentamento|Preven[çc][ãa]o)\b)")
#: Sinal, sintoma ou histórico que antecede a condição e integra o trecho ("sinais de depressão pós-parto").
_PREFIXO_ACHADO = re.compile(r"\b(?:(?:sinais|sintomas|hist[óo]rico|epis[óo]dios?|queixas?)\s+de|"
                             # Ato ou estado do cuidado que governa o termo ("avaliação de prótese", "fila do
                             # transplante", "suspeita de dislexia", "retomada da TARV", "quadro relacionado ao
                             # uso de álcool").
                             r"(?:avalia[çc][ãa]o|consulta|retorno|tratamento|acompanhamento|fila|espera|in[íi]cio|retomada|"
                             r"realiza[çc][ãa]o|coloca[çc][ãa]o|troca|adapta[çc][ãa]o|suspeita|crises?)\s+(?:d[eoa]s?|para|com)|"
                             r"quadro\s+(?:relacionad|associad|decorrent)[oe]\s+(?:a[oa]?|d[eoa]))\s+$", re.IGNORECASE)
#: Contagem antes de termo no plural ("duas internações", "três crises").
_PREFIXO_CONTAGEM = re.compile(rf"\b(?:{_EXTENSO}|\d{{1,2}})\s+$", re.IGNORECASE | re.REVERSE)
_PLURAL = re.compile(r"[a-zà-ú]+(?:[õo]es|s)\b", re.IGNORECASE)
#: Restante da pergunta até o ponto de interrogação, na mesma linha, e resposta afirmativa.
_PERGUNTA = re.compile(r"[^\n?.;]{0,120}\?")
_RESPOSTA_SIM = re.compile(r"[ \t]*(?:\d\s*[–-]\s*)?sim\b", re.IGNORECASE)
#: Termo de cor ou etnia que qualifica serviço, política ou território ("saúde indígena", "educação escolar
#: indígena", "agente indígena de saúde", "comunidades quilombolas").
_RACA_EM_SERVICO = re.compile(r"\b(?:sa[úu]de|educa[çc][ãa]o(?:\s+escolar)?|agente|terra|territ[óo]rio|distrito\s+sanit[áa]rio\s+"
                              r"especial|pol[íi]tica|movimento|povos?|comunidades?|popula[çc][ãa]o|escolas?|aldeias?)\s+$",
                              re.IGNORECASE)
#: Prefixo da origem dos achados do classificador treinado (ver :mod:`themis_lgpd.reconhecedores.aprendido`).
_ORIGEM_APRENDIDA = "aprendido:"
#: Registro em conselho profissional, que marca a linha de assinatura ("Médica oftalmologista – CRM-PB …").
_REGISTRO_PROFISSIONAL = re.compile(r"(?-i:\b(?:CRM|COREN|CRP|CREFITO|CRO|CRFa|CRN|CRESS|CRF|RQE|CRBM|CREF|CRBio)\b)")
#: Fórmula que introduz o conteúdo do atestado ("Atesto, para os devidos fins, que"): fica fora do
#: trecho estendido.
_FORMULA_ATESTACAO = re.compile(r"\b(?:atesto|declaro|certifico|informo|informamos|declaramos)\b[^.;\n]{0,160}?\bque\b",
                                re.IGNORECASE)
#: Cabeçalho de tabela de registro clínico ("EXAME | RESULTADO | REFERÊNCIA", "MEDICAMENTO | DOSE").
_CABECALHO_CLINICO = re.compile(r"\b(?:exames?|resultados?|refer[êe]ncia|medicamentos?|doses?|posologia|achados?|conduta|"
                                r"par[âa]metros?|dom[íi]nios?|qualificador|acuidade|dentes?|inicial|final|(?-i:VR))\b",
                                re.IGNORECASE)


class ContextoDocumental:
    """Características do documento que decidem o vínculo dos dados sensíveis com uma pessoa.

    Cada característica é calculada na primeira consulta: a maior parte dos textos não tem dado sensível,
    e neles o documento não precisa ser classificado.

    Args:
        texto: Texto analisado.
        documento: Classificação do documento inteiro, quando o texto é uma de suas partes (página,
            parágrafo): os campos de identificação da primeira página valem para as seguintes.
        achados_saude: Número de achados de saúde no texto (ver :data:`ACHADOS_DE_REGISTRO_CLINICO`).

    Attributes:
        centrado: O documento trata de uma pessoa identificada (campos de identificação ou fórmula de
            atestação).
        clinico: Além de centrado, é registro clínico ou pericial (título ou seções do registro).
        protegidos: Trechos de nome de instituição, programa ou norma, que permanecem legíveis.
        titulos: Linhas de título (sem minúsculas) em documento de caixa mista.
        linhas_clinicas: Linhas de corpo de tabela de registro clínico (exames, medicamentos, achados),
            tarjadas por inteiro em documento clínico.
        linhas_pessoais: Linhas de tabela com uma pessoa por linha (coluna "Nome", "Candidato"): o dado
            sensível de uma célula se refere à pessoa da linha.
        nomes_proprios: Sequências de palavras com inicial maiúscula no meio da frase, que a extensão do
            trecho de saúde não atravessa.
    """

    def __init__(self, texto: str, documento: ContextoDocumental | None = None, achados_saude: int = 0):
        self.texto = texto
        self._documento = documento
        self.achados_saude = achados_saude

    @cached_property
    def _classificacao(self) -> tuple[bool, bool]:
        texto = self.texto
        titulares = len(_CAMPO_TITULAR.findall(texto))
        rotulos = {dobrar(" ".join(m.group("rotulo").split())) for m in _CAMPO_IDENTIFICACAO.finditer(texto)}
        genero = any(_GENERO_CLINICO.search(linha) for linha in texto[:1500].splitlines()
                     if 0 < len(linha.strip()) <= 110 and ":" not in linha and not linha.rstrip().endswith("."))
        centrado = ((titulares >= 1 and len(rotulos) >= 1) or len(rotulos) >= 3
                    or (genero and bool(titulares or rotulos or _ATESTACAO.search(texto))))
        # Documento centrado em pessoa com muitos achados de saúde é registro clínico mesmo sem título ou
        # seção reconhecidos (relatório em prosa, carta de encaminhamento).
        clinico = centrado and (genero or len(_SECAO_CLINICA.findall(texto)) >= 2
                                or self.achados_saude >= ACHADOS_DE_REGISTRO_CLINICO)
        if self._documento is not None:
            centrado, clinico = centrado or self._documento.centrado, clinico or self._documento.clinico
        return centrado, clinico

    @property
    def centrado(self) -> bool:
        return self._classificacao[0]

    @property
    def clinico(self) -> bool:
        return self._classificacao[1]

    @cached_property
    def socioeducativo(self) -> bool:
        """O documento trata de medida socioeducativa (ver :data:`_SOCIOEDUCATIVO`)."""
        return bool(_SOCIOEDUCATIVO.search(self.texto))

    @cached_property
    def protegidos(self) -> list[tuple[int, int]]:
        return [m.span() for r in (_NOME_INSTITUICAO, _NOME_PROGRAMA, _SIGLA_SERVICO, _NORMA, _SERVICO_COMUM)
                for m in r.finditer(self.texto)]

    @cached_property
    def nomes_proprios(self) -> list[tuple[int, int]]:
        return [m.span() for m in _NOME_PROPRIO.finditer(self.texto)]

    @cached_property
    def titulos(self) -> list[tuple[int, int]]:
        texto = self.texto
        if sum(c.islower() for c in texto) <= 0.3 * sum(c.isalpha() for c in texto):
            return []
        return [m.span() for m in _TITULO.finditer(texto)]

    @cached_property
    def _tabelas(self) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        clinicas, pessoais = [], []
        for cabecalho, linhas in _tabelas(self.texto):
            if self.clinico and (_CABECALHO_CLINICO.search(cabecalho) or _EXAME_RE.search(cabecalho)):
                clinicas += linhas
            if _COLUNA_PESSOA.search(cabecalho):
                pessoais += linhas
        return clinicas, pessoais

    @property
    def linhas_clinicas(self) -> list[tuple[int, int]]:
        return self._tabelas[0]

    @property
    def linhas_pessoais(self) -> list[tuple[int, int]]:
        return self._tabelas[1]

    def em(self, intervalos: list, ini: int, fim: int) -> bool:
        """Indica se o trecho está contido em algum dos intervalos."""
        return any(a <= ini and fim <= b for a, b in intervalos)

    def isencao(self, texto: str, ini: int, fim: int, camada: str, origem: str = "", tipo: str = "",
                pessoal: bool = False) -> str:
        """Motivo para não vincular o termo sensível a uma pessoa, ou ``""``.

        Nome de instituição, programa ou norma e negação valem para qualquer camada; título, linha de
        assinatura e rótulo de campo, só para termos isolados (camada semântica). O nome de exame
        seguido de dois-pontos ("Campo visual (OD): sem alterações") não é rótulo: abre o resultado.
        ``pessoal`` indica marcador de primeira pessoa ou de autodeclaração na frase ("sou um dos 50
        pacientes com esclerose múltipla"): a contagem e a estatística não isentam o termo.
        """
        if self.em(self.protegidos, ini, fim):
            return ISENCAO_NOME
        # Tratamento num serviço citado pelo nome da unidade ("acompanhada no Centro de Atenção Psicossocial
        # Infantojuvenil de Teresina", "no CAPS III Leste"): o nome da unidade é público, e o achado sem ele
        # não descreve condição. O serviço citado pelo tipo ("no CAPS AD", "no ambulatório de saúde mental")
        # continua tarjado com a expressão.
        if (tipo == "SAUDE" and not origem.startswith(_ORIGEM_APRENDIDA)
                and (s := _SERVICO_SAUDE_MENTAL_RE.search(texto, ini, fim)) is not None
                and _servico_nomeado(texto, *s.span()) and not _TERMO_SAUDE.search(texto, ini, s.start())):
            return ISENCAO_NOME
        # Denominação religiosa com inicial maiúscula após outra palavra com inicial maiúscula integra nome
        # próprio de lugar ou de pessoa ("Bernardino Batista", "Vila Adventista").
        if tipo == "RELIGIAO" and texto[ini:ini + 1].isupper() and _NOME_ANTES.search(texto, max(0, ini - 40), ini):
            return ISENCAO_NOME
        # Termo com todas as palavras em inicial maiúscula que continua nome próprio de unidade, cargo ou
        # programa ("Diretora de Atenção a Populações em Situação de Violência").
        if (_TITULO_PROPRIO.fullmatch(texto, ini, fim) and (c := _CONTINUA_NOME.search(texto, max(0, ini - 80), ini))
                and _CABECA_DE_NOME.search(c.group())):
            return ISENCAO_NOME
        if not pessoal and agregado(texto, ini, fim):
            return ISENCAO_AGREGADO
        inicio_linha = texto.rfind("\n", 0, ini) + 1
        if tipo in ("VIOLENCIA", "ORIGEM_RACIAL", "DADO_DE_MENOR") and _CAMPO_CLASSIFICACAO.match(texto, inicio_linha):
            return ISENCAO_CLASSIFICACAO
        # Termo de cor ou etnia com inicial maiúscula após palavra com inicial maiúscula ou sigla integra nome
        # próprio ("Terra Indígena …", "Ribeirão Preto", "SISVAN Indígena").
        if tipo == "ORIGEM_RACIAL" and (texto[ini:ini + 1].isupper() and _NOME_ANTES.search(texto, max(0, ini - 40), ini)
                                         or _RACA_EM_SERVICO.search(texto, max(0, ini - 40), ini)):
            return ISENCAO_NOME
        # Trecho em maiúsculas do classificador treinado sem termo do léxico ("DGDP", "DECLARACAO DE"): sigla
        # ou título. O trecho com dígitos continua tarjado, pois pode ser identificador sem outra regra.
        trecho = texto[ini:fim]
        if (origem.startswith(_ORIGEM_APRENDIDA) and trecho.isupper() and not any(c.isdigit() for c in trecho)
                and not _TERMO_SAUDE.search(texto, ini, fim)):
            return ISENCAO_SIGLA
        if (origem.startswith(_ORIGEM_APRENDIDA) and tipo == "SAUDE" and not _TERMO_SAUDE.search(texto, ini, fim)
                and (_FUNCIONAL_INICIAL.match(texto, ini) or _MEDIDA_DE_OBRA.search(texto, ini, fim))):
            return ISENCAO_FRAGMENTO
        # Expressão de diagnóstico em estatística ou indicador ("o intervalo entre o diagnóstico de câncer e o
        # início da quimioterapia foi de 38 dias em média"), fora de documento sobre pessoa.
        if (origem in ("saude:frase", "saude:cid", "saude:cid-sem-ponto") and not self.centrado and not pessoal
                and _ESTATISTICA.search(texto, *_limites_da_frase(texto, ini, fim))):
            return ISENCAO_AGREGADO
        if (tipo == "SAUDE" and _INTERNACAO_SIMPLES.fullmatch(trecho) and self.socioeducativo
                and not _SERVICO_HOSPITALAR.search(texto, *_limites_da_frase(texto, ini, fim))):
            return ISENCAO_SOCIOEDUCATIVA
        # Negação de registro ("nega alergias", "sem sintomas psicóticos", "Possui deficiência? não"); num
        # pedido, "negou o tratamento" é recusa de terceiro, e não ausência da condição.
        negacao = _NEGACAO_ANTES.search(texto[max(inicio_linha, ini - 60):ini])
        # "Ficou sem a bombinha", "sem insulina": falta do medicamento ou do dispositivo, que revela a
        # condição, e não ausência dela.
        if negacao is not None and negacao.group().lower().startswith("sem") and (
                origem == "saude:medicamento" or _MEDICAMENTO_OU_DISPOSITIVO.match(texto, ini)):
            negacao = None
        if self.centrado and (negacao or _NEGACAO_DEPOIS.match(texto, fim)):
            return ISENCAO_NEGACAO
        # Título ou seção ("LAUDO MÉDICO PARA COMPROVAÇÃO DE DEFICIÊNCIA", "MOTIVO DA INTERNAÇÃO"). O título
        # que enuncia o motivo de saúde de uma licença ou afastamento ("LICENÇA PARA TRATAMENTO DE SAÚDE") e
        # o trecho que traz o número do registro nomeiam o registro de uma pessoa e não são isentos.
        if (self.em(self.titulos, ini, fim) and not _MOTIVO_DE_LICENCA.search(texto, ini, fim)
                and not any(c.isdigit() for c in texto[ini:fim])):
            return ISENCAO_TITULO
        if camada != SEMANTICA:
            return ""
        # Quesito ou pergunta de formulário não respondida com "sim" ("A doença o incapacita para o
        # trabalho? …"): o texto da pergunta é padrão.
        if self.centrado and (q := _PERGUNTA.match(texto, fim)) is not None and not _RESPOSTA_SIM.match(texto, q.end()):
            return ISENCAO_PERGUNTA
        fim_linha = texto.find("\n", fim)
        fim_linha = len(texto) if fim_linha < 0 else fim_linha
        linha = texto[inicio_linha:fim_linha].rstrip()
        if len(linha) <= 100 and not linha.endswith((".", ";", ":")) and _REGISTRO_PROFISSIONAL.search(linha):
            return ISENCAO_ASSINATURA
        # O rótulo pode vir depois de outro campo na mesma linha, separado por travessão, barra vertical,
        # ponto e vírgula, tabulação ou espaços ("DN 01/02/2019 – pessoa com deficiência: …").
        separador = max((p + len(s) for s in (" – ", " | ", ";", "\t", "  ") if (p := texto.rfind(s, inicio_linha, ini)) >= 0),
                        default=-1)
        if (_ROTULO_DEPOIS.match(texto, fim) and not origem.startswith(ORIGEM_CLINICA)
                and (_ANTES_DO_ROTULO.fullmatch(texto, inicio_linha, ini)
                     or separador >= 0 and not texto[separador:ini].strip())):
            return ISENCAO_ROTULO
        return ""

    def estender(self, texto: str, ini: int, fim: int, ancoras: list, limites: list = ()) -> tuple[int, int]:
        """Trecho do dado de saúde estendido até a fronteira da frase ou da célula.

        Num documento clínico, a frase que contém o achado descreve a condição da pessoa: o trecho vai
        até as fronteiras de :data:`_FRONTEIRA`, sem atravessar nome de instituição ou norma nem
        conectivo normativo ("conforme a Política…"). O rótulo da linha ("Diagnóstico:") fica visível,
        salvo quando ele mesmo nomeia um exame ("Biomicroscopia do OE: …"). Fora de documento clínico,
        só a célula de tabela é completada.

        Args:
            texto: Texto analisado.
            ini: Início do achado.
            fim: Fim do achado.
            ancoras: Intervalos dos demais achados de saúde do texto.
            limites: Outros trechos que a extensão não atravessa (municípios citados, por exemplo).
        """
        inicio_linha = texto.rfind("\n", 0, ini) + 1
        fim_linha = texto.find("\n", fim)
        fim_linha = len(texto) if fim_linha < 0 else fim_linha
        if not self.clinico:
            # Atributos da condição: tempo, estado do tratamento, lateralidade, frequência e causa.
            if (p := _PREFIXO_ACHADO.search(texto, max(inicio_linha, ini - 40), ini)) is not None:
                ini = p.start()
            if _PLURAL.match(texto, ini, fim) and (p := _PREFIXO_CONTAGEM.search(texto, max(inicio_linha, ini - 15), ini)):
                ini = p.start()
            b = fim
            while (m := _ATRIBUTO.match(texto, b, fim_linha)) is not None and m.end() > b:
                b = m.end()
            for x, _ in [*self.protegidos, *self.nomes_proprios, *limites]:
                if fim <= x < b:
                    b = x
            linha = texto[inicio_linha:fim_linha]
            if "|" not in linha and "\t" not in linha.strip():
                return self._aparar(texto, ini, b, ini, fim)
            a = max(texto.rfind("|", inicio_linha, ini), texto.rfind("\t", inicio_linha, ini)) + 1 or inicio_linha
            a = max(a, inicio_linha)
            bs = [p for p in (texto.find("|", fim, fim_linha), texto.find("\t", fim, fim_linha)) if p >= 0]
            b = max(b, min(bs) if bs else fim_linha)
            return self._aparar(texto, min(a, ini), max(b, fim), ini, fim)
        a = max((m.end() for m in _FRONTEIRA.finditer(texto, max(0, ini - 600), ini)), default=max(0, ini - 600))
        m = _FRONTEIRA.search(texto, fim, min(len(texto), fim + 600))
        b = m.start() if m else min(len(texto), fim + 600)
        # Rótulo da linha antes de dois-pontos: fica fora, salvo se contiver achado de saúde.
        dois_pontos = texto.find(":", a, ini)
        if dois_pontos >= 0 and dois_pontos - a <= 60 and not any(a <= x < dois_pontos for x, _ in ancoras):
            a = dois_pontos + 1
        for x, y in [*self.protegidos, *self.nomes_proprios, *limites]:
            if a < y <= ini:
                a = y
            if fim <= x < b:
                b = x
        n = _CONECTIVO_NORMATIVO.search(texto, fim, b)
        if n:
            b = n.start()
        formulas = list(_FORMULA_ATESTACAO.finditer(texto, a, ini))
        if formulas:
            a = formulas[-1].end()
        return self._aparar(texto, a, b, ini, fim)

    def recortar(self, texto: str, ini: int, fim: int, achado: tuple[int, int] | None = None) -> list[tuple[int, int]]:
        """Partes do trecho tarjado fora dos nomes de instituição, programa ou norma que ele contém.

        O valor de um campo clínico ("Conduta: encaminhamento ao Núcleo Ampliado de Saúde da Família …")
        pode citar o serviço, que permanece legível. O serviço de saúde mental que o próprio achado descreve
        pelo tipo ("tratamento no CAPS AD", em ``achado``) é o conteúdo do dado e continua tarjado; citado
        pelo nome da unidade ("CAPS Infantojuvenil"), fica legível por inteiro.
        """
        servicos, nomeados = [], []
        for m in (_SERVICO_SAUDE_MENTAL_RE.finditer(texto, *achado) if achado else ()):
            (nomeados if _servico_nomeado(texto, *m.span()) else servicos).append(m.span())
        pecas = [(ini, fim)]
        for x, y in [*self.protegidos, *nomeados]:
            if y <= ini or x >= fim or any(p <= x and y <= q for p, q in servicos):
                continue
            novas = []
            for a, b in pecas:
                if y <= a or x >= b:
                    novas.append((a, b))
                    continue
                if a < x:
                    novas.append((a, x))
                if y < b:
                    novas.append((y, b))
            pecas = novas
        saida = []
        for a, b in pecas:
            # Só as bordas criadas pelo recorte perdem pontuação e palavras funcionais.
            if a != ini and (m := _BORDA_FRACA.match(texto, a, b)):
                a = m.end()
            if b != fim and (m := _BORDA_FRACA_FIM.search(texto, a, b)):
                b = m.start()
            if any(c.isalnum() for c in texto[a:b]):
                saida.append((a, b))
        return saida

    @staticmethod
    def _aparar(texto: str, a: int, b: int, ini: int, fim: int) -> tuple[int, int]:
        """Retira das bordas do trecho estendido pontuação, espaços e palavras funcionais."""
        if a < ini:
            m = _BORDA_FRACA.match(texto, a, ini)
            a = m.end() if m else a
        if b > fim:
            m = _BORDA_FRACA_FIM.search(texto, fim, b)
            b = m.start() if m and m.start() >= fim else b
        return min(a, ini), max(b, fim)


def contexto_documental(texto: str, documento: ContextoDocumental | None = None,
                        achados_saude: int = 0) -> ContextoDocumental:
    """Contexto documental do texto (ver :class:`ContextoDocumental`)."""
    return ContextoDocumental(texto, documento, achados_saude)


def _tabelas(texto: str) -> list[tuple[str, list[tuple[int, int]]]]:
    """Tabelas do texto: o cabeçalho (primeira linha) e os intervalos das linhas do corpo.

    Tabela é a sequência de ao menos duas linhas com separador de célula (``|`` ou tabulação).
    """
    tabelas: list[tuple[str, list[tuple[int, int]]]] = []
    bloco: list[tuple[int, int]] = []
    pos = 0
    for linha in [*texto.split("\n"), ""]:
        if "|" in linha or "\t" in linha.strip():
            bloco.append((pos + len(linha) - len(linha.lstrip()), pos + len(linha)))
        else:
            if len(bloco) >= 2:
                a, b = bloco[0]
                tabelas.append((texto[a:b], [x for x in bloco[1:] if texto[x[0]:x[1]].strip(" |\t-")]))
            bloco = []
        pos += len(linha) + 1
    return tabelas


#: Coluna de tabela que identifica pessoa ("INSCRIÇÃO | NOME | CARGO | DEFICIÊNCIA").
_COLUNA_PESSOA = re.compile(r"\b(?:nome|candidat[oa]|servidor[a]?|paciente|alun[oa]|benefici[áa]ri[oa]|requerente|"
                            r"interessad[oa]|usu[áa]ri[oa])\b", re.IGNORECASE)


# --------------------------------------------------------------------------- Outros sensíveis
#: Templo ou comunidade religiosa e o nome que o segue ("Igreja Adventista do Sétimo Dia", "Renovação
#: Carismática Católica", "Terreiro Ilê Axé …").
_TEMPLO = (r"(?:Igreja|Comunidade\s+(?:Evang[ée]lica|Cat[óo]lica|Luterana|Batista|Presbiteriana|Metodista|Crist[ãa])|Par[óo]quia|"
           r"Congrega[çc][ãa]o|Assembleia\s+de\s+Deus|Centro\s+Esp[íi]rita|Tenda|Renova[çc][ãa]o\s+Carism[áa]tica|"
           r"Templo|Sinagoga|Mesquita|Il[êe](?:\s+Ax[ée])?|Pastoral|capelania|"
           # Casa de culto de matriz africana descrita pela tradição ("casa de xangô", "terreiro de umbanda").
           r"casas?\s+de\s+(?:candombl[ée]|umbanda|santo|ax[ée]|xang[ôo]|mina|batuque|jurema|ora[çc][ãa]o)|"
           r"terreiros?(?:\s+de\s+(?:candombl[ée]|umbanda|batuque|jurema|mina))?)")
#: Denominação após o substantivo ("igreja pentecostal", "Pastoral Carcerária católica").
_DENOMINACAO = (r"(?:evang[ée]lic[oa]s?|pentecosta(?:l|is)|batista|cat[óo]lic[oa]|adventista|presbiterian[oa]|metodista|"
                r"luteran[oa]|crist[ãa]|universal|quadrangular|esp[íi]rita)")
_NOME_TEMPLO = (r"(?:\s+" + _DENOMINACAO + r")*(?:\s+(?:d[aoe]s?\s+|e\s+|n[oa]\s+)?(?-i:[A-ZÀ-Ú][\w'’-]*))*(?:\s+" + _DENOMINACAO
                + r")?(?:\s+d[ao]\s+(?:aldeia|comunidade|assentamento|unidade|vila))?")
_DIA_DA_SEMANA = r"(?:(?:segunda|ter[çc]a|quarta|quinta|sexta)s?(?:[- ]feiras?)?|s[áa]bados?|domingos?)"
#: Função religiosa exercida num templo ("pastor da Igreja …", "iyalorixá do Ilê Axé …", "ogã de uma casa
#: de xangô").
_FUNCAO_RELIGIOSA = (r"(?:pastor[a]?|padre|freira|di[áa]con[oa]|presb[íi]ter[oa]|obreir[oa]|mission[áa]ri[oa]|evangelista|bispo|"
                     r"rabino|im[ãa]|iyalorix[áa]|ialorix[áa]|babalorix[áa]|babala[ôo]|og[ãa]|eked[ei]|equed[ei]|cambon[oa]|"
                     r"m[ãa]e\s+pequena|pai\s+pequeno|zelador[a]?\s+de\s+santo|m[ée]dium|dirigente|catequista|"
                     r"l[íi]der\s+religios[oa])")
#: Sindicato com o complemento que o identifica ("sindicato dos servidores municipais", "Sinpro-DF").
_SINDICATO = (r"(?:sindicato(?:\s+d[aoe]s?\s+(?!(?:e|que)\b)[\wà-ú-]+(?:\s+(?:d[aoe]s?\s+)?(?!(?:e|que|em|para|por|no|na|ao|à|foi|é)\b)"
              r"[\wà-ú-]+){0,2})?|(?-i:Sind[\w-]*|SIND[\w-]*|Sinpro[\w-]*|SINPRO[\w-]*|Sinte[\w-]*|SINTE[\w-]*))")
_CARGO_ELETIVO = (r"(?:vereador[a]?|prefeit[oa]|vice-prefeit[oa]|deputad[oa](?:\s+(?:estadual|federal|distrital))?|senador[a]?|"
                  r"governador[a]?|president[ea])")
#: Termos das demais categorias de dado sensível do art. 5º, II, da LGPD.
SENSIVEIS_SEMANTICA = [
    Padrao("RELIGIAO", _termos(
        r"cat[óo]lic[oa]s?(?:\s+praticantes?)?", r"evang[ée]lic[oa]s?(?:\s+praticantes?)?", r"esp[íi]rita", r"umbandista", r"umbanda",
        r"candombl[ée]", r"candomblecista", r"judeu|judia|judaica?", r"mu[çc]ulman[oa]s?(?:\s+praticantes?)?", r"isl[âa]mic[oa]",
        r"budista", r"hindu[íi]sta", r"ateu|ateia", r"agn[óo]stic[oa]", r"testemunhas?\s+de\s+jeov[áa]",
        r"adventista", r"pentecostal", r"presbiterian[oa]", r"batista", r"m[óo]rmon", r"protestante",
        r"minha\s+(?:religi[ãa]o|f[ée]|cren[çc]a)", r"pr[áa]tica\s+religiosa", r"convic[çc][ãa]o\s+religiosa",
        r"religi[ãa]o\s+de\s+matriz\s+africana", r"luteran[oa]s?", r"anglican[oa]s?", r"metodistas?", r"kardecistas?",
        r"messi[âa]nic[oa]s?",
        # Vínculo com terreiro ou igreja, com o nome do templo ("filha de santo do Terreiro …", "membro da
        # Igreja …", "frequenta os cultos da Comunidade Evangélica …")
        r"(?:filh[oa]|pai|m[ãa]e)\s+de\s+santo(?:\s+(?:d[oe]|em|n[oa])\s+(?:um\s+)?terreiro(?:\s+de\s+\w+|"
        + _NOME_TEMPLO + r")?)?",
        r"iniciad[oa]\s+n[oa]\s+(?:candombl[ée]|umbanda|batuque|jurema)(?:\s+h[áa]\s+(?:\d{1,2}|" + _EXTENSO + r")\s+(?:anos?|meses)|"
        r"\s+em\s+\d{4}|\s+desde\s+(?:\d{4}|crian[çc]a|[oa]\s+\w+))?",
        r"(?:membro|fiel|frequentador[a]?|di[áa]cono|presb[íi]tero|obreir[oa])\s+d[aoe]\s+" + _TEMPLO + _NOME_TEMPLO,
        # Prática religiosa em terceira pessoa ("a família congrega na Igreja …", "frequenta a Paróquia …",
        # "participa das celebrações da Pastoral …").
        r"(?:congrega(?:va|m|vam)?|frequenta(?:va|m|vam|r|ram)?|frequentou|participa(?:va|m)?\s+d[aoe]s?)\s+(?:(?:a|o|as|os|n[ao]s?)\s+)?"
        r"(?:(?:um|uma)\s+)?" + _TEMPLO + _NOME_TEMPLO,
        r"(?:cultos|missas|celebra[çc][õo]es|giras|reuni[õo]es)(?:\s+(?:evang[ée]lic[oa]s|cat[óo]lic[oa]s|religios[oa]s|ecum[êe]nic[oa]s|"
        r"dominicais|semanais))?\s+d[aoe]s?\s+" + _TEMPLO + _NOME_TEMPLO + r"(?:\s+do\s+bairro\s+"
        r"(?-i:[A-ZÀ-Ú][\w-]*)(?:\s+(?-i:[A-ZÀ-Ú][\w-]*))*)?(?:\s+(?:[àa]s|aos|nas|nos)\s+" + _DIA_DA_SEMANA + r")?",
        r"(?:grupos?|c[íi]rculos?|correntes?)\s+de\s+ora[çc][ãa]o(?:\s+d[aoe]\s+" + _TEMPLO + _NOME_TEMPLO + r")?"
        r"(?:\s+(?:[àa]s|aos|nas|nos)\s+" + _DIA_DA_SEMANA + r")?",
        _FUNCAO_RELIGIOSA + r"\s+d[aoe]s?\s+(?:(?:um|uma)\s+)?" + _TEMPLO + _NOME_TEMPLO
        + r"(?:\s+em\s+(?-i:[A-ZÀ-Ú][\w-]+)(?:\s+(?:d[aoe]s?\s+)?(?-i:[A-ZÀ-Ú][\w-]+))*)?",
        # Funções próprias das religiões de matriz africana e das tradições indígenas, que já revelam a
        # pertença ("ogã", "mãe pequena", "ñandesy, rezadora da aldeia").
        r"iyalorix[áa]|ialorix[áa]|babalorix[áa]|babala[ôo]|og[ãa]|eked[ei]|equed[ei]|cambon[oa]|m[ãa]e\s+pequena|"
        r"zelador[a]?\s+de\s+santo",
        r"(?:[ñn]h?andesy|[ñn]h?anderu|paj[ée]|rezador[a]|benzedeir[oa]|xam[ãa])(?:\s*,\s*(?:rezador[a]|benzedeir[oa]|paj[ée]))?"
        r"(?:\s+d[ao]\s+(?:aldeia|comunidade))?",
        r"fio\s+de\s+contas(?:\s+d[eao]\s+(?-i:[A-ZÀ-Ú][\w-]+))?"), 0.8, camada=SEMANTICA),
    Padrao("OPINIAO_POLITICA", _termos(
        # Atuação partidária ou eleitoral de pessoa ("filiada ao mesmo partido do prefeito", "pré-candidata a
        # vereadora pelo Partido …", "fez campanha para o candidato …", "coordenador da campanha do prefeito").
        r"filiad[oa]\s+a[oa]\s+(?:mesmo\s+)?partido(?:\s+d[oa]\s+(?:atual\s+|ex-?)?(?:" + _CARGO_ELETIVO
        + r"|candidat[oa]|secret[áa]ri[oa])(?:\s+(?!(?:e|que)\b)[\wà-ú-]+){0,3})?",
        # A candidatura é pública; o partido pelo qual a pessoa concorre revela a opinião política.
        r"(?:pr[ée]-?)?candidat[oa]\s+a\s+" + _CARGO_ELETIVO + r"\s+pel[oa]\s+(?:(?-i:[A-Z]{2,}[\w-]*)|"
        r"partido(?:\s+(?-i:[A-ZÀ-Ú][\w-]*))+)",
        r"(?:fez|faz|fazia|feito|fazer|fizeram)\s+campanha\s+(?:eleitoral\s+)?(?:para|a\s+favor\s+d[eoa]|contra)\s+(?:[oa]\s+)?"
        r"(?:candidat[oa]|" + _CARGO_ELETIVO + r"|partido|chapa|reelei[çc][ãa]o)[^.;,\n]{0,60}?(?=\s*[.;,\n]|\s+e\s|$)",
        r"(?:coordenador[a]?|cabo\s+eleitoral|tesoureir[oa])\s+da\s+campanha\s+(?:eleitoral\s+)?d[oa]\s+(?:atual\s+|ex-?)?"
        r"(?:candidat[oa]|" + _CARGO_ELETIVO + r")(?:\s+(?!(?:e|que)\b)[\wà-ú-]+){0,2}?(?:\s+em\s+\d{4})?",
        r"filiad[oa]\s+(?:ao|à)\s+(?:partido\s+)?[A-Z][\w-]+(?:\s+(?-i:[A-ZÀ-Ú][\w-]*))*(?:\s*\((?-i:[A-Z]{2,}[\w-]*)\))?"
        r"(?:\s+e\s+membro\s+d[eo]\s+(?:seu\s+)?diret[óo]rio(?:\s+(?:municipal|estadual|nacional|zonal))?)?",
        r"membro\s+d[eo]\s+(?:seu\s+)?diret[óo]rio\s+(?:municipal|estadual|nacional|zonal)", r"militante\s+(?:do|da|de)\s+\w+", r"bolsonarista",
        r"lulista", r"petista", r"tucan[oa]", r"comunista", r"socialista", r"anarquista", r"eleitor(?:a)?\s+(?:do|da|de)\s+\w+",
        r"vot(?:ei|ou|amos|aram)\s+(?:em|no|na)\s+\w+", r"meu\s+voto", r"simpatizante\s+(?:do|da|de)\s+\w+",
        r"opini[ãa]o\s+pol[íi]tica", r"persegui[çc][ãa]o\s+pol[íi]tica", r"posicionamento\s+pol[íi]tico",
        r"sou\s+(?:militante|ativista|filiad[oa]|simpatizante|conservador(?:a)?|progressista|de\s+esquerda|"
        r"de\s+direita|comunista|socialista|anarquista|liberal)", r"minha\s+ideologia",
        r"particip(?:o|ei|amos|ava)\s+d[aoe]s?\s+(?:greve|manifesta[çc][ãa]o|protesto|movimentos?\s+socia(?:l|is)|ato)\w*",
        r"fui\s+candidat[oa](?:\s+a\s+\w+)?", r"membro\s+d[aoe]\s+partido(?:\s+\w+)?"),
        0.8, camada=SEMANTICA),
    Padrao("FILIACAO_SINDICAL", _termos(
        r"sindicalizad[oa]", r"sindicalista",
        r"(?:des)?filiad[oa]\s+(?:ao|à|do|da)\s+sindicato(?:\s+(?:d[aoe]s?\s+|e\s+|em\s+|n[oa]\s+)?(?-i:[A-ZÀ-Ú][\w-]*))*"
        r"(?:\s*\((?-i:[A-Z]{2,}[\w/-]*)(?=\)))?",
        r"mensalidades?\s+sindica(?:l|is)(?:\s*[–-]\s*(?-i:[A-Z]{2,}[\w/-]*))?", r"mensalidades?\s+d[oa]\s+" + _SINDICATO,
        r"(?:des)?filiad[oa]\s+(?:ao|à|do|da)\s+(?-i:Sind[\w-]*|SIND[\w-]*|Sinpro[\w-]*|SINPRO[\w-]*|Sinte[\w-]*|SINTE[\w-]*)",
        # Função sindical ("delegada sindical do Sinpro", "candidato à diretoria do sindicato …").
        r"candidat[oa]\s+[àa]\s+(?:diretoria|dire[çc][ãa]o|presid[êe]ncia)\s+d[oa]\s+" + _SINDICATO,
        r"membro\s+do\s+sindicato(?:\s+\w+)?", r"associad[oa]\s+(?:ao|à)\s+sindicato(?:\s+\w+)?",
        r"dirigente\s+sindical", r"representante\s+sindical", r"delegad[oa]\s+sindical(?:\s+d[oa]\s+" + _SINDICATO + r")?", r"ma[çc]om",
        r"ma[çc]onaria", r"filia[çc][ãa]o\s+sindical", r"membro\s+d[ao]\s+(?:CUT|CTB|UGT|CSP-Conlutas|For[çc]a\s+Sindical)",
        r"diretor(?:a)?\s+do\s+sindicato(?:\s+\w+)?", r"sou\s+sindicalizad[oa]",
        r"sou\s+membro\s+d[aoe]\s+(?:associa[çc][ãa]o|cooperativa|movimento|sindicato)(?:\s+\w+)*?(?=[.,;]|$)"),
        0.85, camada=SEMANTICA),
    Padrao("VIDA_SEXUAL", _termos(
        # Identidade de gênero, orientação e vida sexual descritas por relação ou perífrase ("mantém relações
        # sexuais com …", "relacionamento afetivo com outra interna", "se relacionou com mulheres", "HSH",
        # "se identifica como menina").
        r"(?:mulher|homem)\s+transexual", r"pessoas?\s+n[ãa]o[- ]bin[áa]rias?", r"(?-i:HSH)",
        r"homens\s+que\s+fazem\s+sexo\s+com\s+homens", r"trabalhador[a]?\s+sexual", r"profissional\s+do\s+sexo",
        r"rela[çc](?:[ãa]o|[õo]es)\s+sexua(?:l|is)\s+com\s+[^.;,\n]{2,60}?(?=\s*[.;,\n]|\s+(?:e|quando|mas|porque|pois|que|enquanto)\s|$)",
        r"relacionamento\s+(?:amoroso|afetivo|[íi]ntimo|sexual)\s+com\s+(?:outr[oa]\s+[\wà-ú-]+|(?:um|uma)\s+(?:mulher|homem|rapaz|"
        r"mo[çc]a))",
        r"se\s+relacion(?:a|ava|ou|aram|am)\s+com\s+(?:outr[oa]s\s+)?(?:mulheres|homens|pessoas\s+do\s+mesmo\s+(?:sexo|g[êe]nero))",
        r"parceir[oa]s?\s+(?:fix[oa]s?|sexua(?:l|is)|eventua(?:l|is))",
        r"(?:se\s+identifica|identifica-se|se\s+reconhece|reconhece-se)\s+como\s+(?:menina|menino|mulher|homem|travesti|"
        r"pessoa\s+n[ãa]o[- ]bin[áa]ria|trans\w*|n[ãa]o[- ]bin[áa]ri[oa]|ag[êe]nero|g[êe]nero\s+fluido)",
        r"homossexual", r"heterossexual", r"bissexual", r"pansexual", r"assexual", r"gay", r"l[ée]sbica",
        r"transexual", r"transg[êe]ner[oa]", r"travesti", r"pessoas?\s+trans", r"mulher(?:es)?\s+trans",
        r"home(?:m|ns)\s+trans", r"trans", r"processo\s+transexualizador", r"hormoniza[çc][ãa]o", r"terapia\s+hormonal",
        r"n[ãa]o[- ]bin[áa]ri[oa]", r"intersexo", r"lgbt\w*\+?", r"orienta[çc][ãa]o\s+sexual", r"identidade\s+de\s+g[êe]nero",
        r"vida\s+sexual", r"(?:rela[çc][ãa]o|relacionamento|uni[ãa]o(?:\s+est[áa]vel)?|casamento)\s+homoafetiv[oa]",
        r"homoafetiv[oa]", r"companheir[oa]\s+do\s+mesmo\s+sexo", r"(?:homem|mulher)\s+(?:cis(?:g[êe]nero)?|trans(?:g[êe]nero)?)",
        r"cisg[êe]ner[oa]", r"(?:homo|lesbo|bi|trans)fobia(?:\s*/\s*(?:homo|lesbo|bi|trans)fobia)*", r"lgbt\w*fobia"),
        0.85, camada=SEMANTICA),
    Padrao("GENETICO_BIOMETRICO", _termos(
        r"exame\s+de\s+dna", r"teste\s+(?:de\s+)?(?:dna|gen[ée]tico)", r"perfil\s+gen[ée]tico", r"doen[çc]a\s+gen[ée]tica",
        r"mapeamento\s+gen[ée]tico", r"dados?\s+biom[ée]tricos?", r"biometria(?:\s+facial)?", r"impress[ãa]o\s+digital",
        r"impress[õo]es\s+digitais", r"reconhecimento\s+facial", r"leitura\s+de\s+[íi]ris", r"dados?\s+gen[ée]ticos?"),
        0.85, camada=SEMANTICA),
    Padrao("ORIGEM_RACIAL", _termos(
        r"negr[oa]s?", r"pret[oa]s?", r"pard[oa]s?",
        # Pertença indígena com o gentílico, o povo ou a etnia ("indígena venezuelana do povo Warao", "indígena
        # do povo A'uwẽ (Xavante)", "Indígena Pataxó").
        r"ind[íi]gena(?:\s+(?!d[ao]s?\b)[\wà-ú]+(?:an[oa]|ens[ea]|[êe]s|esa|ian[oa]|in[oa]))?(?:\s+d[ao]s?\s+(?:etnias?|povos?|na[çc][ãa]o)"
        r"\s+(?-i:[A-ZÀ-Ú][\w'’-]*)(?:\s+(?:e\s+)?(?-i:[A-ZÀ-Ú][\w'’-]*))?(?:\s*\((?-i:[A-ZÀ-Ú])[^()\n]{1,25}\))?|"
        r"\s+(?-i:[A-ZÀ-Ú][\w'’-]*))?",
        # Pertença cigana ou quilombola da pessoa ou da família ("família cigana", "ciganos da etnia Rom …",
        # "família quilombola Kalunga") e pertença a um povo ("pertence ao povo Kaiowá").
        r"(?:fam[íi]lias?\s+|pessoas?\s+)?cigan[oa]s?(?:\s+d[ao]\s+etnia\s+(?-i:[A-ZÀ-Ú][\w'’-]*)(?:\s+(?!(?:e|que|de|da|do|em|no|na)\b)"
        r"[\w'’-]+)?|\s+(?-i:Calon|Rom|Sinti)\b)?",
        r"(?:fam[íi]lias?|pessoas?)\s+quilombolas?(?:\s+(?-i:[A-ZÀ-Ú][\w'’-]*))?",
        r"(?<=\b(?:pertence(?:m)?|pertencia(?:m)?|[ée]|s[ãa]o|era|eram)\s+(?:a[oa]|à|d[oa])\s+)povos?\s+(?-i:[A-ZÀ-Ú][\w'’-]*)"
        r"(?:\s+(?-i:[A-ZÀ-Ú][\w'’-]*))?",
        r"quilombola",
        r"remanescentes?\s+de\s+quilombos?", r"afrodescendentes?",
        r"afro-?brasileir[oa]s?", r"autodeclarad[oa]\s+\w+", r"cor\s+da\s+pele", r"origem\s+(?:[ée]tnica|racial)",
        r"etnia\s+\w+", r"ra[çc]a\s+(?!(?:declarad|autodeclarad|informad|registrad)\w*)\w+", r"cotista\s+racial", r"racismo",
        r"inj[úu]ria\s+racial",
        r"comunidade\s+(?:quilombola|ind[íi]gena|cigana)"), 0.75, camada=SEMANTICA),
    # Campo de cor ou raça de ficha ou cadastro ("Raça/cor: parda", "Raça/cor: Indígena (etnia …)").
    Padrao("ORIGEM_RACIAL", r"\b(?:ra[çc]a\s*/\s*cor|cor\s*/\s*ra[çc]a|cor\s+(?:da\s+pele|ou\s+ra[çc]a)|ra[çc]a(?:\s+ou\s+cor)?|etnia)"
                            r"(?:\s+(?:declarad[oa]|autodeclarad[oa]|informad[oa])(?:\s+[^:\n]{0,40}?)?)?\s*:\s*"
                            r"(branc[oa]|pret[oa]|pard[oa]|amarel[oa]|ind[íi]gena(?:\s*\([^()\n]{1,30}\))?)(?!\w)",
           0.9, camada=CONTEXTUAL, grupo=1, nome="sensivel:raca-cor"),
]
#: Valor de campo de cadastro: até o fim da linha, o separador de colunas ou o rótulo seguinte; campo vazio
#: ou respondido com "não", "nenhuma" ou "não informado" fica de fora.
_VALOR_DE_CAMPO = (r"[ \t]*:[ \t]*(?!(?:n[ãa]o|nenhum[a]?|sem|nega|n/?a|---?|—)\b)([^\s:|;(\[_][^\n:|;]{1,60}?)"
                   r"(?=[ \t]*[.;|]?[ \t]*$|[ \t]{2,}|[ \t]*[|;]|[ \t]+(?-i:[A-ZÀ-Ú])[\wÀ-ú.]*(?:[ \t]+[\wÀ-ú.]+)?[ \t]*:)")
# Mandato classista, licença do servidor para exercer cargo na direção do sindicato (Lei nº 8.112/1990, art.
# 92): sempre de pessoa determinada.
SENSIVEIS_SEMANTICA.append(
    Padrao("FILIACAO_SINDICAL", r"\b(?:liberad[oa]\s+para\s+|licen[çc]a\s+para\s+(?:o\s+)?(?:desempenho\s+de\s+)?)?mandato\s+classista"
                                r"(?:\s+n[ao]\s+(?:diretoria|dire[çc][ãa]o|executiva)\s+d[oa]\s+" + _SINDICATO + r")?\b", 0.85,
           camada=CONTEXTUAL, nome="sensivel:mandato-classista"))
# Campo de ficha ou cadastro que declara o dado sensível da pessoa ("Identidade de gênero: mulher trans",
# "Pertencimento étnico: quilombola", "GPTE declarado: família cigana", "Religião: candomblé").
SENSIVEIS_SEMANTICA += [
    Padrao("VIDA_SEXUAL", r"\b(?:identidade\s+de\s+g[êe]nero|orienta[çc][ãa]o\s+sexual)(?:\s+(?:declarad[oa]|informad[oa]))?"
           + _VALOR_DE_CAMPO, 0.9, camada=CONTEXTUAL, grupo=1, nome="sensivel:campo"),
    Padrao("RELIGIAO", r"\b(?:religi[ãa]o|cren[çc]a\s+religiosa|denomina[çc][ãa]o\s+religiosa)(?:\s+(?:declarad[oa]|informad[oa]))?"
           + _VALOR_DE_CAMPO, 0.9, camada=CONTEXTUAL, grupo=1, nome="sensivel:campo"),
    Padrao("ORIGEM_RACIAL", r"\b(?:pertencimento(?:\s+[ée]tnico)?|(?-i:GPTE)|grupos?\s+(?:populaciona(?:l|is)\s+)?tradiciona(?:l|is)"
                            r"(?:\s+e\s+espec[íi]fico)?|povo\s+ind[íi]gena|comunidade\s+tradicional)(?:\s+(?:declarad[oa]|"
                            r"informad[oa]|autodeclarad[oa]))?" + _VALOR_DE_CAMPO, 0.9, camada=CONTEXTUAL, grupo=1,
           nome="sensivel:campo"),
]

# --------------------------------------------------------------------------- Intimidade e risco (LAI art. 31)
#: Relatos de violência e de situação de risco. A divulgação pode expor a vítima a nova violência;
#: por isso a confiança é alta e a camada é contextual.
_TIPO_VIOLENCIA = (r"viol[êe]ncia\s+(?:dom[ée]stica|familiar|sexual|f[íi]sica|psicol[óo]gica|patrimonial|obst[ée]trica|"
                   r"contra\s+a\s+mulher)|abuso\s+(?:sexual|f[íi]sico|psicol[óo]gico)|estupro(?:\s+de\s+vulner[áa]vel)?|"
                   r"ass[ée]dio\s+(?:moral|sexual)|amea[çc]as?\s+de\s+morte|c[áa]rcere\s+privado|"
                   r"tentativa\s+de\s+(?:homic[íi]dio|feminic[íi]dio|suic[íi]dio)|feminic[íi]dio|explora[çc][ãa]o\s+sexual|"
                   r"tr[áa]fico\s+de\s+pessoas|inj[úu]ria\s+racial")
INTIMIDADE_CONTEXTUAL = [
    # Tipo de violência atribuído a alguém ("vítima de", "sofreu", "medo de", "alvo de"). O tipo citado
    # sem enquadramento ("o canal recebe denúncias de assédio moral") é termo isolado (ver
    # :data:`INTIMIDADE_SEMANTICA`).
    Padrao("VIOLENCIA", r"\b(?:medo|v[íi]tima|sofr(?:e|o|i|endo|eu|ia)|alvo)\s+de\s+(?:" + _TIPO_VIOLENCIA + r")",
           0.95, camada=CONTEXTUAL, nome="intimidade:violencia"),
    # Classificação do caso pelo técnico ("Considerando tratar-se, em tese, de estupro de vulnerável", "caso
    # notificado como violência psicológica").
    Padrao("VIOLENCIA", r"(?<=\b(?:tratar-se|trata-se|tratando-se)(?:,?\s+em\s+tese,?)?\s+de\s+|"
                        r"\b(?:caso|fato|situa[çc][ãa]o|ocorr[êe]ncia)\s+(?:foi\s+)?(?:classificad|tipificad|notificad|enquadrad)[oa]\s+"
                        r"como\s+)(?:" + _TIPO_VIOLENCIA + r")", 0.9, camada=CONTEXTUAL, nome="intimidade:classificacao"),
    # Relatos em primeira pessoa de ameaça, agressão, fuga ou risco à vida.
    Padrao("VIOLENCIA",
           r"\b(?:estou\s+em\s+perigo|corro\s+risco|fugindo\s+de\s+casa|preciso\s+de\s+abrigo|casa[- ]abrigo|"
           r"escolta\s+policial|medo\s+de\s+denunciar|n[ãa]o\s+tenho\s+para\s+onde\s+ir|vai\s+me\s+matar|"
           r"amea[çc]ou\s+me\s+matar|me\s+amea[çc](?:a|ou|ando)|me\s+persegue|me\s+agrid(?:e|iu)|me\s+bate|me\s+bateu|"
           r"me\s+espanc\w+|me\s+humilh\w+|marcas\s+no\s+corpo|quebrou\s+a\s+medida|agredid[oa]\s+(?:pel[oa]|por)\s+\w+|"
           r"sofr(?:o|i)\s+(?:agress[õo]es|amea[çc]as|viol[êe]ncia)|recebi\s+amea[çc]as|tentou\s+me\s+\w+|"
           r"medo\s+de\s+(?:sofrer\s+)?(?:viol[êe]ncia|apanhar|agress[ãa]o|morrer|ser\s+morta?)|"
           r"me\s+vigia|controla\s+tudo|"
           r"fugi\s+de\s+casa|amea[çc]a\s+levar\s+(?:meus|minhas|os|as)\s+filh[oa]s|apanh(?:ar|ei|o)\s+(?:de|do|da|novamente)|"
           r"tentativa\s+de\s+suic[íi]dio|pensamentos\s+suicidas|idea[çc][ãa]o\s+suicida|automutila[çc][ãa]o)",
           0.95, camada=CONTEXTUAL, nome="intimidade:risco"),
]
#: Termos isolados de vida privada: violência, conflitos familiares, situação prisional.
INTIMIDADE_SEMANTICA = [
    Padrao("VIOLENCIA", _termos(r"agress[ãa]o", r"agress[õo]es", r"viol[êe]ncia", r"medo\s+de\s+retalia[çc][ãa]o",
                                r"agredid[oa]", r"amea[çc]ad[oa]", r"espancad[oa]", r"abusad[oa]",
                                r"violentad[oa]", r"suic[íi]dio", r"trai[çc][ãa]o", r"div[óo]rcio", r"separa[çc][ãa]o\s+"
                                r"(?:conjugal|judicial)", r"guarda\s+(?:dos?\s+filhos?|"
                                r"compartilhada|unilateral)", r"usu[áa]ri[oa]\s+de\s+drogas", r"presidi[áa]ri[oa]",
                                r"egress[oa]\s+do\s+sistema\s+prisional", r"antecedentes\s+criminais", r"condenad[oa]"),
            0.75, camada=SEMANTICA, nome="intimidade:termo"),
    # Tipo de violência sem enquadramento, medida protetiva e situação de risco ou de vulnerabilidade:
    # tarjados quando a frase se refere a pessoa determinada ("estou em situação de risco").
    Padrao("VIOLENCIA", r"\b(?:" + _TIPO_VIOLENCIA + r"|medida\s+protetiva(?:\s+de\s+urg[êe]ncia)?|"
                        r"situa[çc][ãa]o\s+de\s+(?:risco|viol[êe]ncia|vulnerabilidade))\b",
           0.85, camada=SEMANTICA, nome="intimidade:tipo"),
]

# --------------------------------------------------------------------------- Menores (LGPD art. 14)
#: Referências a criança ou adolescente determinado e a situações protegidas pelo ECA.
MENOR_CONTEXTUAL = [
    # Criança ou adolescente com a idade ("meu filho de 8 anos"): a idade, combinada ao vínculo
    # familiar do requerente, identifica o menor.
    # Faixas e limites de idade ("crianças de 6 meses a menores de 9 anos", "menores de 15 anos") são
    # critério de norma ou de estatística e ficam legíveis; o plural sem determinante designa um grupo.
    Padrao("DADO_DE_MENOR",
           r"\b(?:(?:minhas?|meus?|suas?|seus?|as?|os?)\s+(?:crian[çc]as|beb[êe]s|adolescentes|filh[oa]s|net[oa]s|entead[oa]s|"
           r"menin[oa]s|dependentes)|(?:(?:minha|meu|sua|seu|a|o)\s+)?(?:crian[çc]a|beb[êe]|adolescente|filh[oa]|net[oa]|"
           r"entead[oa]|menin[oa]|dependente))\s+(?:de|com)\s+\d{1,2}\s+(?:anos?|meses)(?:\s+de\s+idade)?"
           r"(?!\s*(?:a|e|at[ée])\s+(?:menores\s+de\s+)?\d)", 0.9, camada=CONTEXTUAL, nome="menor:idade"),
    # Medidas e procedimentos do ECA cuja divulgação é vedada (arts. 17 e 143).
    Padrao("DADO_DE_MENOR",
           r"\b(?:medida\s+socioeducativa|ato\s+infracional|"
           r"abrigo\s+de\s+menores|guarda\s+provis[óo]ria|destitui[çc][ãa]o\s+do\s+poder\s+familiar|"
           r"processo\s+de\s+ado[çc][ãa]o|menor\s+infrator(?:a)?|menor\s+sob\s+guarda|menor\s+de\s+idade\s+sob\s+\w+\s+"
           r"(?:responsabilidade|guarda|tutela)|menor\s+[óo]rf[ãa]o?|sob\s+tutela(?:\s+do\s+estado)?|"
           r"crian[çc]a\s+em\s+situa[çc][ãa]o\s+de\s+(?:abrigo|rua|risco|acolhimento))", 0.85, camada=CONTEXTUAL,
           nome="menor:situacao"),
]
#: Órgão e serviço de proteção citados sem a criança ("o conselho tutelar do bairro", "vagas de
#: acolhimento institucional"): tarjados quando a frase se refere a pessoa determinada. O acolhimento de
#: adultos e de idosos não é medida do ECA.
MENOR_SEMANTICA = [
    Padrao("DADO_DE_MENOR", r"\b(?:conselho\s+tutelar|acolhimento\s+institucional(?!\s+(?:para\s+)?(?:de\s+)?(?:adultos|"
                            r"idosos|pessoas\s+idosas|fam[íi]lias|mulheres)))\b",
           0.85, camada=SEMANTICA, nome="menor:servico"),
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
    r"conciliador(?:a)?", r"mediador(?:a)?", r"candidat[oa]",
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
    # Trabalho rural, doméstico e comunitário
    r"vaqueir[oa]", r"capataz", r"caseir[oa]", r"tratorista", r"diarista", r"bab[áa]", r"s[íi]ndic[oa]",
    r"l[íi]der(?:\s+comunit[áa]ri[oa])?", r"conselheir[oa]\s+tutelar",
    # Postos militares e policiais, que designam a pessoa pelo posto ("a soldado que dirigia a viatura")
    r"soldado", r"sargento", r"subtenente", r"tenente", r"delegad[oa]",
    # Vizinhança, descrita pela moradia ("a vizinha do apartamento 22")
    r"vizinh[oa]",
    # Referência coloquial a quem atendeu
    r"rapaz", r"mo[çc][oa]",
)
#: Pessoas designadas pela condição, e não pela função ("o único apenado da galeria", "a única interna
#: da unidade", "a única pessoa que visita a idosa"): só formam quase-identificador depois de "único".
_CONDICOES = (
    r"apenad[oa]", r"intern[oa]", r"reeducand[oa]", r"detent[oa]", r"pres[oa]", r"acolhid[oa]",
    r"morador(?:a)?", r"residente", r"pessoa", r"mulher", r"homem", r"crian[çc]a", r"adolescente", r"jovem",
    r"alun[oa]", r"estudante", r"paciente", r"usu[áa]ri[oa]", r"idos[oa]", r"empregad[oa]",
    r"trabalhador(?:a)?", r"profissional", r"integrante", r"membro", r"candidat[oa]", r"benefici[áa]ri[oa]",
)
#: Palavra que introduz a função como pessoa: artigo, contração, demonstrativo, possessivo, "como",
#: verbos de ligação ("sou motorista", "trabalhei como vigilante"), "na função de" e "na qualidade de"
#: ou rótulo ("Servidor envolvido:"). No início da linha, a função com inicial maiúscula é o conteúdo de
#: um campo ("TESTEMUNHA\nPorteiro do turno da manhã").
_INTRODUZ = (r"(?:(?<=(?:(?:^|[^\w])(?:o|a|um|uma|do|da|no|na|pelo|pela|ao|à|num|numa|dum|duma|"
             r"(?:d|n|daqu|naqu|aqu)?(?:est|ess|el)[ea]|aquel[ea]|como|sou|era|fui|é|foi|seu|sua|meu|minha|nosso|"
             r"nossa|pr[oa]s?|prum|pruma|(?:fun[çc][ãa]o|qualidade|condi[çc][ãa]o)\s+de)\s+)|:\s*)"
             r"|^(?=(?-i:[A-ZÀ-Ú])))")
#: "Segurança", "guarda municipal" e "caixa" só designam a pessoa no masculino ("o segurança", "o guarda
#: municipal", "pelo caixa do guichê 2"); no feminino, são o conceito ("a segurança do paciente"), a
#: corporação e o objeto.
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
_SINTAGMA = (rf"(?:{_DETERMINANTE}\s+)?(?:[úu]nic[oa]s?\s+)?(?:\d{{1,3}}[oaºª°]?\s+(?=(?-i:[A-ZÀ-Ú])){_NUCLEO}(?:\s+{_MODIFICADOR}){{0,2}}|"
             rf"{_NUMERO}|{_NUCLEO}(?:\s+{_MODIFICADOR}){{0,4}}"
             rf"(?:\s+{_NUMERO}|\s+(?-i:[A-Z])\b)?)")
#: Primeira palavra da oração relativa, que deve ser o verbo: não pode ser artigo, pronome ou conjunção.
_NAO_VERBO = (r"(?:o|a|os|as|um|uma|ele|ela|eles|elas|eu|voc[êe]s?|n[ãa]o|que|e|ou|se|me|nos|lhe|"
              r"meus?|minhas?|seus?|suas?|nossos?|nossas?|est[ea]s?|ess[ea]s?|d[oa]s?|de|n[oa]s?|em|para|pra|por|com)")
_DIA_SEMANA = r"(?:(?:segunda|ter[çc]a|quarta|quinta|sexta)s?(?:[- ]feiras?)?|s[áa]bados?|domingos?)"
_MES = r"(?:janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
#: Particípios que, em aposto, situam a pessoa ("lotada na escola", "atribuída a um único reeducando").
_PARTICIPIO = (r"(?:situad|localizad|lotad|designad|escalad|atribu[íi]d|identificad|conhecid|apelidad|chamad|"
               r"vinculad|incumbid)[oa]s?")
#: Aposto que descreve a pessoa ("um senhor grisalho de bigode").
_PESSOA_DESCRITA = r"(?:um|uma)\s+(?:senhor|senhora|homem|mulher|rapaz|mo[çc]a|jovem|idos[oa])"
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
    # "para", "por" e "após" seguidos de sintagma nominal ("para as reeducandas surdas", "por pavilhão",
    # "após o fechamento"), mas não de infinitivo nem de locução ("para pedir", "por isso").
    rf"(?:para|ap[óo]s)\s+(?:{_DETERMINANTE}\s+)?(?!\w+(?:ar|er|ir)\b){_NUCLEO}(?:\s+{_MODIFICADOR}){{0,2}}",
    rf"por\s+(?!(?:isso|meio|exemplo|favor|fim|conta|causa|vezes|que|volta)\b)(?!\w+(?:ar|er|ir)\b){_NUCLEO}",
    # Oração relativa com preposição ou "onde": "da escola em que o adolescente estuda".
    rf"(?:(?:em|n[oa])\s+que|n[oa]s?\s+qua(?:l|is)|onde)\s+(?:{_DETERMINANTE}\s+)?{_NUCLEO}(?:\s+{_PALAVRA})?",
    # Apostos: "única docente do local", "um senhor grisalho", "responsável pela distribuição",
    # "lotada na unidade"; dias da semana enumerados ("de segunda, quarta e sexta-feira").
    rf"[úu]nic[oa]s?\s+{_NUCLEO}(?:\s+{_MODIFICADOR}){{0,2}}",
    rf"{_PESSOA_DESCRITA}(?:\s+{_MODIFICADOR}){{0,3}}",
    rf"respons[áa]vel|{_PARTICIPIO}|{_DIA_SEMANA}",
    # Turno ou período em aposto ("da turma do 5º ano B, turno vespertino").
    rf"(?:turno|per[íi]odo|plant[ãa]o|escala)(?:\s+{_MODIFICADOR}){{1,2}}",
)
#: Vírgula seguida de novo complemento de tempo ou lugar: "ontem, dia 10, por volta das 15h".
_VIRGULA = (r"\s*,\s*(?=(?:n[oa]s?|num|numa|em|entre|durante|desde|at[ée]|sentido|por\s+volta|que|dia|ontem|"
            r"anteontem|hoje|l[áa]|[úu]nic[oa]s?|respons[áa]vel|turno|per[íi]odo|plant[ãa]o|escala|" + _PARTICIPIO + "|" + _PESSOA_DESCRITA + "|"
            + _DIA_SEMANA + r")\b|(?:[àa]s?|d[ao]s|de)\s+\d)")
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
    r"enfermaria|prefixo|setor|gleba|trecho|poste|apartamento|apto|casa|pavilh[ãa]o|galeria|cela|alojamento|"
    r"barraco)\s+(?:n[º°o.]?\s*)?(?:\d+\w*|(?-i:[A-Z])\b)"
    r"|\b(?:ao\s+lado|em\s+frente)\b"
    r"|\bd[ao]\s+(?:fazenda|s[íi]tio|ch[áa]cara|edif[íi]cio|condom[íi]nio|est[âa]ncia|granja)\s+(?-i:[A-ZÀ-Ú])"
    r"|\bque\s+(?:me|nos|lhe)\s+\w+"
    r"|\bque\s+\w+(?:ou|eu|iu|ava|ia|eve|ez|eio)\b"
    r"|\bque\s+(?:atua|atende|trabalha|fica|faz|d[áa]|passa|circula|opera|coordena|leciona|cuida|acompanha|"
    r"conduz|presta)\b"
    r"|\brespons[áa]vel\s+pel[oa]s?\b|\bencarregad[oa]\s+d[eoa]s?\b|\bde\s+plant[ãa]o\b|\b[úu]nic[oa]\s",
    re.IGNORECASE)
_FUNCAO = (rf"(?:{_INTRODUZ}(?:ex-)?(?:(?:atual|[úu]nic[oa]|mesm[oa]|referid[oa])\s+)?(?:{'|'.join(_FUNCOES)})"
           rf"|{_INTRODUZ_MASC}(?:seguran[çc]a|guarda\s+(?:municipal|civil|patrimonial)|"
           rf"caixa(?!\s+(?:eletr[ôo]nico|econ[ôo]mica|d['’]?[áa]gua|postal|de\s+(?:entrada|som|correio|texto))))"
           # "Único" já determina a pessoa, mesmo sem artigo ("a noticiante, única professora surda da escola").
           rf"|(?<![\w])[úu]nic[oa]\s+(?:{'|'.join(_FUNCOES + _CONDICOES)}))(?:-chefe)?\b")


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


#: Marcas físicas que distinguem uma pessoa de outras: tatuagem, cicatriz, piercing, modo de andar ou de
#: falar, prótese.
_MARCA_FISICA = re.compile(
    r"\b(?:tatuage(?:m|ns)|cicatriz(?:es)?|piercings?|manc(?:o|a|ava|ando)|marcas?\s+de\s+nascen[çc]a|"
    r"sinal\s+de\s+nascen[çc]a|dentes?\s+de\s+ouro|pr[óo]tese|muletas?|gag(?:o|a|uejava)|olho\s+de\s+vidro|"
    r"sem\s+(?:um|o|os|dois)\s+dedos?)\b", re.IGNORECASE)
#: Pessoa descrita pela aparência, sem nome ("o mais alto, com tatuagem de escorpião no pescoço", "um
#: homem magro, de boné, que mancava"): suspeitos e testemunhas em boletins e termos de declaração.
_DESCRICAO_FISICA = (
    r"(?<=\b(?:o|a|um|uma|ao|à|do|da)\s+)(?:mais\s+(?:alt|baix|velh|nov|magr|gord|fort)[oa]|homem|mulher|rapaz|"
    r"mo[çc]a|jovem|indiv[íi]duo|suspeit[oa]|sujeito|elemento|senhor|senhora|autor[a]?)"
    rf"(?:\s+{_MODIFICADOR}){{0,3}}(?:(?:\s*,\s*|\s+)(?:e\s+)?(?:com|de|usando|vestindo|portando|que)\s+[^,.;\n]{{1,80}}){{1,4}}"
)


class _PadraoMarcaFisica(Padrao):
    """:class:`Padrao` cujo achado só é aceito se descrever uma marca física distintiva."""

    def detectar(self, texto: str) -> list:
        return [d for d in super().detectar(texto) if _MARCA_FISICA.search(texto, d.inicio, d.fim)]


QUASE_IDENTIFICADORES = [
    _PadraoIndividualizado("QUASE_IDENTIFICADOR", _FUNCAO + rf"(?:\s+{_MODIFICADOR}){{0,2}}(?:{_CADEIA}){{1,12}}",
                           0.6, camada=CONTEXTUAL, nome="quase:funcao-complemento"),
    _PadraoMarcaFisica("QUASE_IDENTIFICADOR", _DESCRICAO_FISICA, 0.6, camada=CONTEXTUAL, nome="quase:descricao-fisica"),
]


def reconhecedores():
    """Reconhecedores deste módulo, na forma esperada por :mod:`themis_lgpd.analisador`."""
    return [
        ReconhecedorPadroes("saude", SAUDE_CONTEXTUAL + SAUDE_SEMANTICA + SAUDE_CLINICA),
        ReconhecedorPadroes("sensiveis", SENSIVEIS_SEMANTICA),
        ReconhecedorPadroes("intimidade", INTIMIDADE_CONTEXTUAL + INTIMIDADE_SEMANTICA),
        ReconhecedorPadroes("menores", MENOR_CONTEXTUAL + MENOR_SEMANTICA),
        ReconhecedorPadroes("quase_identificadores", QUASE_IDENTIFICADORES),
    ]
