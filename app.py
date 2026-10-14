import streamlit as st
import pdfplumber
import google.generativeai as genai
import pandas as pd
import plotly.express as px
import json
import time

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Analizator Konspektów ZHP", page_icon="⚜️", layout="wide")

# --- DEFINICJE METODY HARCERSKIEJ ---
METODA_HARCERSKA = [
    "Dobrowolność", 
    "Pozytywność", 
    "Pośredniość", 
    "Indywidualizacja", 
    "Naturalność", 
    "Świadomość celów", 
    "Wzajemne oddziaływanie"
]

# --- FUNKCJE POMOCNICZE ---
def wyciagnij_tekst_z_pdf(plik_pdf):
    """Pobiera tekst z pliku PDF i dzieli go na akapity."""
    tekst_caly = ""
    with pdfplumber.open(plik_pdf) as pdf:
        for strona in pdf.pages:
            tekst_strony = strona.extract_text()
            if tekst_strony:
                tekst_caly += tekst_strony + "\n"
    
    # Dzielimy na akapity (zakładamy, że podwójny enter to nowy akapit)
    akapity = [akapit.strip() for akapit in tekst_caly.split('\n\n') if len(akapit.strip()) > 50]
    return akapity

def analizuj_akapit_ai(akapit, klucz_api):
    """Wysyła akapit do modelu Gemini w celu wyszukania elementów metody."""
    # WPISUJEMY KLUCZ NA SZTYWNO:
    genai.configure(api_key="AIzaSyCsuBhHyvyOfvhnc6LJV6ioy0qai8Kx-84") 
    
    # Używamy Gemini 1.5 Flash
    model = genai.GenerativeModel('gemini-2.0-flash', 
                                  generation_config={"response_mime_type": "application/json"})
    
    
    prompt = f"""
    Jesteś badaczem analizującym konspekty zajęć Związku Harcerstwa Polskiego (ZHP).
    Twoim zadaniem jest sprawdzenie, czy poniższy fragment tekstu realizuje któryś z elementów metody harcerskiej.
    
    Elementy do wyboru:
    - Dobrowolność (wolny wybór, chęć działania)
    - Pozytywność (skupienie na zaletach, zachęta)
    - Pośredniość (nauka przez działanie, gra, zabawa)
    - Indywidualizacja (dostosowanie do osoby, rozwój talentów)
    - Naturalność (działanie w małej grupie, w przyrodzie)
    - Świadomość celów (zrozumienie sensu działania)
    - Wzajemne oddziaływanie (praca w zespole, starsi uczą młodszych)
    
    Przeanalizuj poniższy tekst i zwróć wynik w formacie JSON z dwoma kluczami:
    "znalezione_elementy": lista stringów (tylko dokładne nazwy elementów z listy wyżej, jeśli nie ma żadnego, zostaw pustą listę []),
    "uzasadnienie": krótkie jednozdaniowe uzasadnienie dlaczego te elementy zostały wybrane.
    
    Tekst do analizy:
    "{akapit}"
    """
    
    try:
        response = model.generate_content(prompt)
        wynik_json = json.loads(response.text)
        return wynik_json
    except Exception as e:
        return {"znalezione_elementy": [], "uzasadnienie": f"Błąd analizy: {str(e)}"}

# --- INTERFEJS UŻYTKOWNIKA (UI) ---
st.title("⚜️ Narzędzie Badawcze: Analiza Metody Harcerskiej")
st.markdown("Wgraj konspekt w formacie PDF, a sztuczna inteligencja przeanalizuje go pod kątem występowania elementów metody harcerskiej.")

# Pasek boczny na konfigurację
with st.sidebar:
    st.header("⚙️ Konfiguracja")
    api_key = st.text_input("Podaj klucz Google Gemini API", type="password", help="Klucz pobierzesz za darmo z Google AI Studio.")
    st.markdown("---")
    st.markdown("**Metoda harcerska:**")
    for element in METODA_HARCERSKA:
        st.markdown(f"- {element}")

# Obszar główny - wgrywanie pliku
plik = st.file_uploader("Wybierz plik z konspektem (PDF)", type=['pdf'])

if plik is not None:
    if not api_key:
        st.warning("⚠️ Proszę podać klucz API Gemini w panelu bocznym, aby rozpocząć analizę.")
    else:
        if st.button("🚀 Rozpocznij analizę"):
            with st.spinner("Ekstrakcja tekstu z PDF..."):
                akapity = wyciagnij_tekst_z_pdf(plik)
            
            st.info(f"Znaleziono {len(akapity)} fragmentów tekstu do analizy.")
            
            # Pasek postępu
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            wyniki_zbiorcze = []
            
            # Główna pętla analityczna
            for i, akapit in enumerate(akapity):
                status_text.text(f"Analizowanie fragmentu {i+1} z {len(akapity)}...")
                
                wynik_ai = analizuj_akapit_ai(akapit, api_key)
                
                wyniki_zbiorcze.append({
                    "Fragment konspektu": akapit,
                    "Znalezione Elementy": ", ".join(wynik_ai.get("znalezione_elementy", [])),
                    "Uzasadnienie": wynik_ai.get("uzasadnienie", "")
                })
                
                # Aktualizacja paska postępu
                progress_bar.progress((i + 1) / len(akapity))
                time.sleep(1) # Lekkie opóźnienie, by nie przekroczyć limitów darmowego API
                
            status_text.text("✅ Analiza zakończona!")
            
            # --- PRZETWARZANIE WYNIKÓW I WIZUALIZACJA ---
            df = pd.DataFrame(wyniki_zbiorcze)
            
            st.subheader("📊 Wyniki analizy")
            
            # Liczenie wystąpień poszczególnych elementów
            zliczenia = {element: 0 for element in METODA_HARCERSKA}
            for elementy_str in df["Znalezione Elementy"]:
                if elementy_str:
                    dla_tego_wiersza = [e.strip() for e in elementy_str.split(",")]
                    for e in dla_tego_wiersza:
                        if e in zliczenia:
                            zliczenia[e] += 1
                            
            df_zliczenia = pd.DataFrame(list(zliczenia.items()), columns=["Element Metody", "Liczba wystąpień"])
            
            # Wykres radarowy
            col1, col2 = st.columns(2)
            
            with col1:
                fig_radar = px.line_polar(df_zliczenia, r='Liczba wystąpień', theta='Element Metody', line_close=True,
                                        title="Nasycenie konspektu metodą harcerską",
                                        color_discrete_sequence=['#4CAF50'])
                fig_radar.update_traces(fill='toself')
                st.plotly_chart(fig_radar, use_container_width=True)
                
            with col2:
                fig_bar = px.bar(df_zliczenia, x='Element Metody', y='Liczba wystąpień', 
                                 title="Rozkład wystąpień (szczegółowy)",
                                 color='Liczba wystąpień', color_continuous_scale='Greens')
                st.plotly_chart(fig_bar, use_container_width=True)
            
            # Tabela ze szczegółami
            st.subheader("📝 Szczegółowa analiza fragmentów")
            st.dataframe(df, use_container_width=True)