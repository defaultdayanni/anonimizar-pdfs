import re
import sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import fitz


EMAIL_RE = re.compile(r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])", re.IGNORECASE)
CPF_RE = re.compile(r"(?<!\d)(?:\d{3}[.\s-]?\d{3}[.\s-]?\d{3}[\s-]?\d{2})(?!\d)")


def cpf_valido(valor: str) -> bool:
    numeros = re.sub(r"\D", "", valor)
    if len(numeros) != 11 or numeros == numeros[0] * 11:
        return False

    for tamanho in (9, 10):
        soma = sum(int(numeros[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11
        if digito == 10:
            digito = 0
        if digito != int(numeros[tamanho]):
            return False
    return True


def _variantes_cpf(cpf: str) -> set[str]:
    numeros = re.sub(r"\D", "", cpf)
    return {
        cpf,
        numeros,
        f"{numeros[:3]}.{numeros[3:6]}.{numeros[6:9]}-{numeros[9:]}",
        f"{numeros[:3]} {numeros[3:6]} {numeros[6:9]} {numeros[9:]}",
    }


def localizar_dados(texto: str) -> tuple[set[str], set[str]]:
    emails = {m.group(0) for m in EMAIL_RE.finditer(texto)}
    cpfs = {m.group(0) for m in CPF_RE.finditer(texto) if cpf_valido(m.group(0))}
    return emails, cpfs


def anonimizar_pdf(entrada: str | Path, saida: str | Path) -> dict[str, int]:
    entrada = Path(entrada)
    saida = Path(saida)
    if entrada.resolve() == saida.resolve():
        raise ValueError("O arquivo de saída deve ser diferente do original.")

    documento = fitz.open(entrada)
    if documento.needs_pass:
        documento.close()
        raise ValueError("O PDF está protegido por senha.")

    total_emails = 0
    total_cpfs = 0
    total_tarjas = 0

    try:
        for pagina in documento:
            texto = pagina.get_text("text")
            emails, cpfs = localizar_dados(texto)
            encontrados_na_pagina: set[tuple[float, float, float, float]] = set()

            termos: list[tuple[str, str]] = [(email, "email") for email in emails]
            for cpf in cpfs:
                termos.extend((variante, "cpf") for variante in _variantes_cpf(cpf))

            tipos_encontrados: set[tuple[str, str]] = set()
            for termo, tipo in termos:
                for retangulo in pagina.search_for(termo):
                    chave = tuple(round(v, 2) for v in retangulo)
                    if chave in encontrados_na_pagina:
                        continue
                    encontrados_na_pagina.add(chave)
                    tipos_encontrados.add((tipo, termo))
                    margem = 1.2
                    area = fitz.Rect(
                        retangulo.x0 - margem,
                        retangulo.y0 - margem,
                        retangulo.x1 + margem,
                        retangulo.y1 + margem,
                    )
                    pagina.add_redact_annot(area, fill=(0, 0, 0))

            if encontrados_na_pagina:
                pagina.apply_redactions()
                total_tarjas += len(encontrados_na_pagina)
                total_emails += len({termo for tipo, termo in tipos_encontrados if tipo == "email"})
                cpfs_localizados = {
                    re.sub(r"\D", "", termo)
                    for tipo, termo in tipos_encontrados
                    if tipo == "cpf"
                }
                total_cpfs += len(cpfs_localizados)

        saida.parent.mkdir(parents=True, exist_ok=True)
        documento.save(saida, garbage=4, deflate=True, clean=True)
    finally:
        documento.close()

    return {"emails": total_emails, "cpfs": total_cpfs, "tarjas": total_tarjas}


def pasta_do_programa() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def anonimizar_pasta(pasta: str | Path) -> dict[str, object]:
    pasta = Path(pasta)
    arquivos = sorted(
        arquivo
        for arquivo in pasta.glob("*.pdf")
        if not arquivo.stem.lower().endswith("_anonimiza")
    )
    resultados: list[dict[str, object]] = []

    for entrada in arquivos:
        saida = entrada.with_name(f"{entrada.stem}_anonimiza.pdf")
        contagem = anonimizar_pdf(entrada, saida)
        resultados.append({"entrada": entrada, "saida": saida, **contagem})

    return {"quantidade": len(resultados), "arquivos": resultados}


class Aplicativo(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Anonimizador de PDF")
        self.geometry("700x285")
        self.resizable(False, False)
        self.pasta = pasta_do_programa()
        self.status = tk.StringVar(value="Clique no botão para anonimizar os PDFs da pasta.")
        self._montar_tela()

    def _montar_tela(self) -> None:
        quadro = ttk.Frame(self, padding=24)
        quadro.pack(fill="both", expand=True)

        ttk.Label(quadro, text="Anonimizador de PDF", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(
            quadro,
            text="Processa todos os PDFs pesquisáveis que estiverem junto do executável.",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(2, 18))

        ttk.Label(quadro, text="Pasta analisada:", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        ttk.Label(quadro, text=str(self.pasta), wraplength=645).pack(anchor="w", pady=(2, 12))

        self.botao = ttk.Button(quadro, text="Anonimizar todos os PDFs", command=self.processar)
        self.botao.pack(anchor="w", pady=(2, 16))
        ttk.Label(quadro, textvariable=self.status, wraplength=595).pack(anchor="w")

    def processar(self) -> None:
        self.botao.configure(state="disabled")
        self.status.set("Processando os PDFs da pasta...")
        self.update_idletasks()
        try:
            resultado = anonimizar_pasta(self.pasta)
            quantidade = int(resultado["quantidade"])
            if quantidade == 0:
                self.status.set("Nenhum PDF novo foi encontrado.")
                messagebox.showinfo(
                    "Nenhum arquivo",
                    "Não há PDFs para processar nesta pasta.\n"
                    "Arquivos terminados em _anonimiza.pdf são ignorados.",
                )
                return

            arquivos = resultado["arquivos"]
            total_emails = sum(int(item["emails"]) for item in arquivos)
            total_cpfs = sum(int(item["cpfs"]) for item in arquivos)
            total_tarjas = sum(int(item["tarjas"]) for item in arquivos)
            resumo = (
                f"{quantidade} PDF(s) processado(s).\n"
                f"{total_emails} e-mail(s), {total_cpfs} CPF(s) e {total_tarjas} tarja(s).\n\n"
                "Os novos arquivos terminam em _anonimiza.pdf."
            )
            self.status.set(f"Concluído: {quantidade} PDF(s) anonimizado(s).")
            messagebox.showinfo("Concluído", resumo)
        except Exception as erro:
            self.status.set("Não foi possível anonimizar o PDF.")
            messagebox.showerror("Erro", str(erro))
        finally:
            self.botao.configure(state="normal")


def main() -> None:
    if len(sys.argv) == 3:
        resultado = anonimizar_pdf(sys.argv[1], sys.argv[2])
        print(resultado)
        return
    Aplicativo().mainloop()


if __name__ == "__main__":
    main()
