# GlobalVoice — Landing Page

Landing page estática para o produto GlobalVoice. Publicada via GitHub Pages.

## Estrutura
docs/site/
├── index.html # Página principal
├── style.css # Estilos
├── assets/
│ └── favicon.svg # Ícone do site
└── README.md

## Como publicar (GitHub Pages)

1. Faça commit dos arquivos em `docs/site/`.
2. No GitHub, vá em **Settings → Pages**.
3. Em **Source**, selecione:
   - **Branch:** `main`
   - **Folder:** `/docs`
4. Clique em **Save**.
5. O site estará disponível em `https://GlobalVoice-Uni.github.io/GlobalVoice-Desktop/site/`.

## Personalização

### Link de download

No `index.html`, procure por `id="download-button"` e atualize o `href` com o link do instalador:

```html
<a href="https://github.com/GlobalVoice-Uni/GlobalVoice-Desktop/releases/latest/download/GlobalVoice-Setup-0.1.0.exe" class="btn btn-light btn-lg" id="download-button">

## Para rodar o comando pra teste local 
hash
cd docs\site
python -m http.server 8000
 
 resposta terminal esperada: Serving HTTP on :: port 8000 (http://[::]:8000/) ...

   Após a resposta no terminal-> Abra http://localhost:8000 no navegador.