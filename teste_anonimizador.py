import tempfile
from pathlib import Path

import fitz

from anonimizador_pdf import anonimizar_pasta, anonimizar_pdf, cpf_valido, localizar_dados


def testar_validacao() -> None:
    assert cpf_valido("529.982.247-25")
    assert cpf_valido("52998224725")
    assert not cpf_valido("111.111.111-11")
    assert not cpf_valido("529.982.247-24")


def testar_localizacao() -> None:
    emails, cpfs = localizar_dados("Contato: aluno.teste+curso@exemplo.com CPF 529.982.247-25")
    assert emails == {"aluno.teste+curso@exemplo.com"}
    assert cpfs == {"529.982.247-25"}


def testar_redacao() -> None:
    with tempfile.TemporaryDirectory() as pasta:
        entrada = Path(pasta) / "entrada.pdf"
        saida = Path(pasta) / "saida.pdf"

        doc = fitz.open()
        pagina = doc.new_page()
        pagina.insert_text((72, 72), "Email: aluno@exemplo.com")
        pagina.insert_text((72, 100), "CPF: 529.982.247-25")
        doc.save(entrada)
        doc.close()

        resultado = anonimizar_pdf(entrada, saida)
        assert resultado["emails"] == 1
        assert resultado["cpfs"] == 1
        assert resultado["tarjas"] == 2

        anonimizado = fitz.open(saida)
        texto = "".join(p.get_text() for p in anonimizado)
        anonimizado.close()
        assert "aluno@exemplo.com" not in texto
        assert "529.982.247-25" not in texto


def testar_processamento_em_lote() -> None:
    with tempfile.TemporaryDirectory() as pasta_temporaria:
        pasta = Path(pasta_temporaria)
        for nome in ("primeiro.pdf", "segundo.pdf"):
            doc = fitz.open()
            pagina = doc.new_page()
            pagina.insert_text((72, 72), "Contato: aluno@exemplo.com")
            doc.save(pasta / nome)
            doc.close()

        resultado = anonimizar_pasta(pasta)
        assert resultado["quantidade"] == 2
        assert (pasta / "primeiro_anonimiza.pdf").exists()
        assert (pasta / "segundo_anonimiza.pdf").exists()

        segunda_execucao = anonimizar_pasta(pasta)
        assert segunda_execucao["quantidade"] == 2
        assert not (pasta / "primeiro_anonimiza_anonimiza.pdf").exists()


if __name__ == "__main__":
    testar_validacao()
    testar_localizacao()
    testar_redacao()
    testar_processamento_em_lote()
    print("Todos os testes passaram.")
