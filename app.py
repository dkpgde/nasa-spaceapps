"""Run with: streamlit run app.py. This slice needs no weather/network access."""
from datetime import date, timedelta
import altair as alt
import pandas as pd
import streamlit as st
from rotationlab.catalog import load_catalog
from rotationlab.model import RotationPlan, expand_rotation

st.set_page_config(page_title="RotationLab · Crop timeline", page_icon="🌱", layout="wide")
data, calendars = load_catalog()
st.title("RotationLab")
st.caption("IOWA CROP PLANNING · SOURCED CALENDAR")
st.header("See the season before comparing the weather")
st.write("A four-year corn–soybean calendar with planned living cover and visible assumptions.")
with st.sidebar:
    st.header("Timeline settings")
    start_year = int(st.number_input("First year", min_value=1901, max_value=2096, value=2017, step=1))
    starting_crop = st.selectbox("Starting crop", ["Grain corn", "Soybean"])
    start = st.date_input("Coverage starts", date(start_year, 1, 1),
                          min_value=date(start_year, 1, 1), max_value=date(start_year + 3, 12, 31), key=f"start-{start_year}")
    end = st.date_input("Coverage ends", date(start_year + 3, 12, 31),
                        min_value=date(start_year, 1, 1), max_value=date(start_year + 3, 12, 31), key=f"end-{start_year}")
    st.caption("Dates are supplied independently of NASA weather retrieval. Partial coverage clips the calendar.")
if start > end or start.year != start_year:
    st.error("Coverage must start in the first year and end on or after its start.")
    st.stop()
plan = RotationPlan("Corn → soybean", ("grain_corn", "soybean"),
                    0 if starting_crop == "Grain corn" else 1, ("marsden",))
timeline = expand_rotation(plan, start, end, calendars)
location, soil = data["location"], data["soil"]
a, b, c = st.columns(3)
a.metric("Representative location", "Boone County, IA")
a.caption(f"Marsden study area · {location['latitude']:.4f}, {location['longitude']:.4f}")
b.metric("Surface texture", soil["texture"])
b.caption(soil["name"])
c.metric("Available calendar coverage", f"{start.year}–{end.year}")
c.caption(f"{start.isoformat()} → {end.isoformat()} · inclusive")
st.subheader("Crop sequence")
st.write(" → ".join(f"{y.year} {calendars[y.crop_id].name}" for y in timeline.years))
st.caption(f"Preceding phase: {calendars[timeline.years[0].preceding_crop_id].name}. "
           "This annual rotation has no overwinter living cover; preceding crop residue is not counted.")

labels = {"planting":"Planting window", "harvest":"Usual harvest window",
          "living_cover":"Planned living cover", "sensitive":"Sensitive growth window"}
rows = [{"Crop year": f"{w.crop_year} · {calendars[w.crop_id].name}",
         "Window": labels[w.kind], "Start": w.start.isoformat(), "End": w.end.isoformat(),
         "Plot end": (w.end + timedelta(days=1)).isoformat(),
         "Basis": w.assumption, "Sources": ", ".join(w.sources)}
        for w in timeline.windows if w.kind in labels]
st.subheader("Calendar & planned living cover")
st.caption("Green indicates planned living cover. Other bars show operation ranges and a sensitive-stage date proxy. "
           "Blank months mean no planned living cover in this sourced annual plan, not bare soil or zero erosion.")
frame = pd.DataFrame(rows)
if rows:
    chart = alt.Chart(frame).mark_bar(cornerRadius=3, height=11).encode(
        x=alt.X("Start:T", title=None, scale=alt.Scale(domain=[start.isoformat(), (end + timedelta(days=1)).isoformat()]), axis=alt.Axis(format="%b %Y", labelAngle=-35)),
        x2="Plot end:T", y=alt.Y("Crop year:N", sort=None, title=None),
        yOffset=alt.YOffset("Window:N", sort=list(labels.values())),
        color=alt.Color("Window:N", scale=alt.Scale(domain=list(labels.values()), range=["#d6a33d", "#a77950", "#39865a", "#7867ad"]), legend=alt.Legend(orient="bottom", title=None, columns=2, labelLimit=0, columnPadding=14)),
        tooltip=["Crop year:N", "Window:N", "Start:N", "End:N", "Basis:N", "Sources:N"]
    ).properties(height=max(170, 80 * len(timeline.years)))
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("The supplied coverage contains no calendar intervals. The rules are available; the clipped result is empty.")
st.info("Living-cover and sensitive-window dates are fixed demo assumptions, not measured crop stages. "
        "This timeline does not estimate yield, soil moisture, erosion or actual field access.")
with st.expander("Inspect exact dates and assumptions", expanded=False):
    st.dataframe(frame.drop(columns=["Plot end"]) if rows else frame, hide_index=True, use_container_width=True)
    st.download_button("Download interval dates (CSV)", frame.drop(columns=["Plot end"]).to_csv(index=False) if rows else "", "rotationlab-timeline.csv", "text/csv")
with st.expander("Soil context & profile"):
    st.write(soil["drainage"])
    st.write(soil["note"])
    st.dataframe(pd.DataFrame(soil["horizons"]), hide_index=True, use_container_width=True)
with st.expander("Calendar rules, availability & sources", expanded=True):
    for assumption in data["assumptions"]:
        st.write(f"• {assumption}")
    st.caption("Availability is exposed per crop year and rule category: unavailable differs from available with no intervals.")
    st.dataframe(pd.DataFrame([{"Year": y.year, "Crop": calendars[y.crop_id].name,
        "Termination": timeline.query(y.year, y.crop_id, "termination").availability.value,
        "Termination intervals": len(timeline.query(y.year, y.crop_id, "termination").intervals)} for y in timeline.years]), hide_index=True)
    for key, source in data["sources"].items():
        st.markdown(f"**[{source['title']}]({source['url']})** · `{key}`")
        st.caption(source["basis"])
