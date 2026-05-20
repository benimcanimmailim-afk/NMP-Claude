import urllib.request
import base64
import os

fonts = {
    "JetBrains Mono": {
        300: "https://fonts.gstatic.com/s/jetbrainsmono/v24/tDbY2o-flEEny0FZhsfKu5WU4zr3E_BX0PnT8RD8lqxjPQ.ttf",
        400: "https://fonts.gstatic.com/s/jetbrainsmono/v24/tDbY2o-flEEny0FZhsfKu5WU4zr3E_BX0PnT8RD8yKxjPQ.ttf",
        500: "https://fonts.gstatic.com/s/jetbrainsmono/v24/tDbY2o-flEEny0FZhsfKu5WU4zr3E_BX0PnT8RD8-qxjPQ.ttf",
        600: "https://fonts.gstatic.com/s/jetbrainsmono/v24/tDbY2o-flEEny0FZhsfKu5WU4zr3E_BX0PnT8RD8FqtjPQ.ttf",
        700: "https://fonts.gstatic.com/s/jetbrainsmono/v24/tDbY2o-flEEny0FZhsfKu5WU4zr3E_BX0PnT8RD8L6tjPQ.ttf"
    },
    "Exo 2": {
        300: "https://fonts.gstatic.com/s/exo2/v26/7cH1v4okm5zmbvwkAx_sfcEuiD8j4PKcPg.ttf",
        400: "https://fonts.gstatic.com/s/exo2/v26/7cH1v4okm5zmbvwkAx_sfcEuiD8jvvKcPg.ttf",
        600: "https://fonts.gstatic.com/s/exo2/v26/7cH1v4okm5zmbvwkAx_sfcEuiD8jYPWcPg.ttf",
        700: "https://fonts.gstatic.com/s/exo2/v26/7cH1v4okm5zmbvwkAx_sfcEuiD8jWfWcPg.ttf",
        900: "https://fonts.gstatic.com/s/exo2/v26/7cH1v4okm5zmbvwkAx_sfcEuiD8jF_WcPg.ttf"
    }
}

css_output = ""

for family, weights in fonts.items():
    for weight, url in weights.items():
        print(f"Downloading {family} {weight}...")
        try:
            with urllib.request.urlopen(url) as response:
                content = response.read()
                b64 = base64.b64encode(content).decode('utf-8')
                css_output += f"""
@font-face {{
  font-family: '{family}';
  font-style: normal;
  font-weight: {weight};
  font-display: swap;
  src: url(data:font/ttf;base64,{b64}) format('truetype');
}}"""
        except Exception as e:
            print(f"Failed to download {url}: {e}")

with open("embedded_fonts.css", "w") as f:
    f.write(css_output)
print("CSS with embedded fonts generated in embedded_fonts.css")
