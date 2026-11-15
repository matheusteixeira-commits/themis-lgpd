"""Gera as listas de prenomes, sobrenomes e nomes ambíguos usadas pelo reconhecedor de nomes.

As listas são gravadas em ``src/themis_lgpd/dados``, uma entrada por linha, em minúsculas e sem
acentos — a mesma forma produzida por :func:`themis_lgpd.texto.dobrar` na comparação.

Fontes: listas pt_BR do Faker (licença MIT) e nomes frequentes no Brasil compilados manualmente;
nomes próprios isolados não são objeto de proteção autoral.

Uso::

    python scripts/gerar_listas_nomes.py
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

from faker.providers.person.pt_BR import Provider

#: Prenomes frequentes no Brasil ausentes ou sub-representados nas listas do Faker.
PRENOMES_EXTRA = [
    "maria", "jose", "ana", "joao", "antonio", "francisco", "carlos", "paulo", "pedro", "lucas", "luiz",
    "luis", "marcos", "luciana", "gabriel", "rafael", "daniel", "marcelo", "bruno", "eduardo", "felipe",
    "raimundo", "rodrigo", "manoel", "manuel", "mateus", "matheus", "andre", "fernando", "fabio", "leonardo",
    "gustavo", "guilherme", "leandro", "tiago", "thiago", "anderson", "ricardo", "marcio", "jorge",
    "alexandre", "roberto", "edson", "diego", "vitor", "victor", "sergio", "claudio", "cesar", "vinicius",
    "wellington", "adriana", "juliana", "marcia", "fernanda", "patricia", "aline", "sandra", "camila",
    "amanda", "bruna", "jessica", "leticia", "julia", "luana", "mariana", "gabriela", "vanessa", "simone",
    "renata", "vera", "debora", "tatiana", "larissa", "beatriz", "raquel", "rosangela", "rosana", "rosimeire",
    "cristina", "cristiane", "claudia", "carla", "priscila", "eliane", "elaine", "luciene", "jaqueline",
    "natalia", "sonia", "regina", "andreia", "andrea", "angela", "daniela", "michele", "michelle", "sabrina",
    "tania", "silvia", "lucia", "helena", "isabela", "isabel", "francisca", "antonia", "aparecida",
    "conceicao", "fatima", "graca", "socorro", "raimunda", "terezinha", "tereza", "teresa", "josefa",
    "marlene", "edna", "edileuza", "ivone", "ivonete", "irene", "iracema", "joana", "luzia", "lourdes",
    "neide", "nilza", "odete", "rita", "sebastiana", "severina", "benedito", "benedita", "sebastiao",
    "severino", "joaquim", "geraldo", "valdir", "valter", "walter", "wagner", "washington", "wesley",
    "willian", "william", "wilson", "jefferson", "jonas", "jonathan", "juliano", "julio", "junior", "kleber",
    "leonel", "levi", "lorenzo", "miguel", "arthur", "heitor", "theo", "davi", "bernardo", "samuel", "enzo",
    "murilo", "benjamin", "henrique", "joaquim", "lorena", "valentina", "helena", "alice", "laura", "manuela",
    "sophia", "sofia", "heloisa", "isadora", "livia", "giovanna", "lara", "melissa", "yasmin", "cecilia",
    "clara", "eloa", "nicole", "agatha", "emanuelly", "rebeca", "esther", "ester", "vitoria", "luisa",
    "luiza", "marina", "carolina", "caroline", "jaine", "kelly", "karina", "karen", "katia", "keila", "kesia",
    "adriano", "alan", "alberto", "alessandro", "alex", "alexsandro", "alisson", "allan", "altamiro", "amaro",
    "ademir", "adilson", "ailton", "airton", "alcides", "alvaro", "anselmo", "apolonio", "armando", "arnaldo",
    "augusto", "aurelio", "baltazar", "bento", "bernardino", "caio", "calebe", "celso", "cicero", "clovis",
    "cristiano", "cristovao", "danilo", "davi", "decio", "denis", "dennis", "diogo", "domingos", "douglas",
    "edgar", "edilson", "edivaldo", "edmilson", "edmundo", "edvaldo", "elias", "eliseu", "elton", "emerson",
    "enio", "erasmo", "erick", "erico", "ernesto", "eugenio", "evandro", "everaldo", "everton", "ezequiel",
    "fabiano", "fabricio", "felix", "flavio", "franklin", "frederico", "gaspar", "genival", "gerson",
    "getulio", "gilberto", "gilmar", "gilson", "giovani", "glauco", "gregorio", "heitor", "helio", "hercules",
    "hermes", "hilario", "hugo", "humberto", "icaro", "igor", "inacio", "irineu", "isaac", "isaias", "ismael",
    "israel", "italo", "ivan", "jacinto", "jackson", "jair", "jairo", "janio", "jeferson", "jeronimo", "joel",
    "jordao", "josias", "josue", "juarez", "juca", "juscelino", "laercio", "lauro", "leo", "leonidas",
    "lindomar", "lino", "lourival", "luan", "lucio", "luciano", "manuela", "marcel", "marciano", "marcolino",
    "mario", "martim", "mauricio", "mauro", "max", "maximo", "milton", "moacir", "moises", "murilo", "nadir",
    "natanael", "nelson", "nestor", "newton", "nicolas", "nilson", "nilton", "noel", "norberto", "octavio",
    "olavo", "onofre", "orlando", "osmar", "osvaldo", "otavio", "pablo", "patrick", "percival", "rai", "raul",
    "reinaldo", "renan", "renato", "robson", "rogerio", "romario", "romulo", "ronaldo", "rubens", "ruan",
    "rui", "samuel", "saulo", "silvio", "simao", "tadeu", "tales", "tarcisio", "teodoro", "tomas", "tulio",
    "ubiratan", "ulisses", "valdemar", "valmir", "vanderlei", "vicente", "vinicio", "waldir", "wanderley",
    "yuri", "zacarias", "abigail", "adelaide", "adelia", "adriele", "agnes", "alessandra", "alexandra",
    "alicia", "alzira", "amelia", "ana-paula", "anita", "barbara", "berenice", "betania", "bianca", "brenda",
    "camila", "carmem", "carmen", "celia", "celina", "cibele", "cintia", "clarice", "cleide", "cleonice",
    "creuza", "dalva", "dayane", "denise", "dirce", "dolores", "doralice", "dulce", "edilene", "edite",
    "elisa", "elisabete", "elizabete", "eloisa", "elza", "emilia", "erica", "estela", "eunice", "evelyn",
    "fabiana", "fabiola", "flavia", "gilda", "gisele", "glaucia", "gleice", "heloise", "hilda", "iara",
    "ingrid", "irani", "isis", "ivana", "ivete", "jamile", "janaina", "jane", "janete", "jordana", "josiane",
    "joyce", "judite", "jussara", "karla", "kassia", "lais", "lea", "leila", "lidia", "lilian", "liliane",
    "lindalva", "luana", "lucelia", "luciane", "ludmila", "madalena", "maiara", "mara", "marcela",
    "margarete", "maria-eduarda", "marilene", "marilia", "marisa", "marlucia", "marta", "mayara", "miriam",
    "monica", "nadia", "nair", "nara", "neusa", "nubia", "olga", "paloma", "paula", "pamela", "poliana",
    "rafaela", "regiane", "rejane", "roberta", "rosa", "rosilene", "roseli", "rute", "ruth", "samara",
    "samira", "selma", "shirley", "silvana", "silvania", "solange", "stefany", "suelen", "suely", "sueli",
    "talita", "tamires", "thais", "valeria", "vania", "veronica", "viviane", "wanessa", "zilda", "zuleide",
]

#: Sobrenomes frequentes no Brasil, incluindo os agnomes "filho", "neto" e "junior".
SOBRENOMES_EXTRA = [
    "silva", "santos", "oliveira", "souza", "sousa", "rodrigues", "ferreira", "alves", "pereira", "lima",
    "gomes", "costa", "ribeiro", "martins", "carvalho", "almeida", "lopes", "soares", "fernandes", "vieira",
    "barbosa", "rocha", "dias", "nascimento", "andrade", "moreira", "nunes", "marques", "machado", "mendes",
    "freitas", "cardoso", "ramos", "goncalves", "santana", "teixeira", "araujo", "cavalcante", "cavalcanti",
    "melo", "mello", "moura", "campos", "batista", "monteiro", "correia", "correa", "medeiros", "duarte",
    "miranda", "pinto", "barros", "castro", "azevedo", "nogueira", "farias", "fonseca", "guimaraes", "coelho",
    "reis", "borges", "brito", "sampaio", "pires", "siqueira", "matos", "mattos", "paiva", "amaral", "moraes",
    "morais", "cruz", "leite", "cunha", "prado", "tavares", "rezende", "resende", "viana", "vasconcelos",
    "albuquerque", "arruda", "bezerra", "brandao", "macedo", "meireles", "menezes", "magalhaes", "queiroz",
    "rangel", "sales", "salles", "serra", "torres", "xavier", "aguiar", "alencar", "assis", "assuncao",
    "bastos", "benevides", "bittencourt", "bonfim", "braga", "bueno", "caldeira", "camargo", "cardoso",
    "carneiro", "chaves", "damasceno", "domingues", "dornelas", "estevam", "evangelista", "falcao", "feitosa",
    "figueiredo", "franco", "frota", "galvao", "garcia", "gusmao", "holanda", "jesus", "leal", "leao",
    "lacerda", "lobo", "luz", "maciel", "maia", "malta", "mesquita", "mota", "motta", "nobrega", "novaes",
    "novais", "pacheco", "padilha", "pimentel", "pinheiro", "porto", "quintela", "ramalho", "rios", "rosa",
    "sa", "sena", "sobrinho", "tome", "toledo", "valente", "vargas", "veloso", "viegas", "vilela", "vital",
    "fagundes", "fontes", "peixoto", "aragao", "amorim", "antunes", "avila", "bandeira", "barreto", "belo",
    "cabral", "calixto", "camelo", "candido", "castilho", "coutinho", "cordeiro", "diniz", "drummond",
    "esteves", "fialho", "frazao", "gaspar", "godoy", "guerra", "hora", "jardim", "lessa", "louro", "marinho",
    "modesto", "montenegro", "muniz", "neves", "nunes", "ornelas", "pacifico", "pessoa", "portela",
    "quaresma", "rabelo", "rabello", "saldanha", "seixas", "severo", "simoes", "tenorio", "uchoa",
    "valadares", "veras", "zanetti", "filho", "neto", "junior",
]

#: Nomes que também são palavras comuns ("rosa", "luz", "campos", "torres"). Só iniciam um nome
#: quando escritos com inicial maiúscula e nunca são propagados isoladamente.
AMBIGUOS = [
    "rosa", "clara", "luz", "graca", "paz", "gloria", "vitoria", "aurora", "celeste", "estrela", "flor",
    "mar", "sol", "bela", "dores", "neves", "cruz", "socorro", "lima", "vida", "alegria", "branca", "perola",
    "rainha", "serena", "esperanca", "fe", "piedade", "amparo", "lua", "jade", "iris", "violeta", "margarida",
    "dalia", "jasmim", "angelica", "regina", "augusto", "justo", "severo", "prudente", "bento", "leao",
    "lobo", "coelho", "pinto", "carneiro", "cordeiro", "rocha", "mercedes", "cristal", "safira", "ametista",
    "hortencia", "camelia", "lirio", "orquidea", "primavera", "mel", "doce", "felicidade", "valente",
    "franco", "modesto", "belo", "santana", "santa", "sao", "vale", "campos", "ramos", "flores", "fontes",
    "porto", "rios", "serra", "torres", "guerra",
]


def dobrar(s: str) -> str:
    """Minúsculas e sem acentos (o script não depende do pacote instalado)."""
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if not unicodedata.combining(c))


def main() -> None:
    """Gera os três arquivos.

    Nomes compostos ("ana-paula") são descartados, pois o reconhecedor compara palavra a palavra.
    """
    destino = Path(__file__).resolve().parents[1] / "src" / "themis_lgpd" / "dados"
    destino.mkdir(parents=True, exist_ok=True)
    prenomes = {dobrar(n) for n in list(Provider.first_names_female) + list(Provider.first_names_male)}
    prenomes |= {dobrar(n).replace("-", " ") for n in PRENOMES_EXTRA}
    prenomes = {p for p in prenomes if " " not in p and len(p) > 1}
    sobrenomes = {dobrar(n) for n in Provider.last_names} | {dobrar(n) for n in SOBRENOMES_EXTRA}
    sobrenomes = {s for s in sobrenomes if " " not in s and len(s) > 1}
    cab = "# Gerado por scripts/gerar_listas_nomes.py — minúsculas, sem acentos\n"
    (destino / "prenomes.txt").write_text(cab + "\n".join(sorted(prenomes)) + "\n", encoding="utf-8")
    (destino / "sobrenomes.txt").write_text(cab + "\n".join(sorted(sobrenomes)) + "\n", encoding="utf-8")
    (destino / "nomes_ambiguos.txt").write_text(cab + "\n".join(sorted({dobrar(a) for a in AMBIGUOS})) + "\n",
                                                encoding="utf-8")
    print(f"{len(prenomes)} prenomes, {len(sobrenomes)} sobrenomes, {len(AMBIGUOS)} ambíguos")


if __name__ == "__main__":
    main()
