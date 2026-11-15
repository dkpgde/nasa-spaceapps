const { Deck, GeoJsonLayer, PolygonLayer, IconLayer, MapView, _GlobeView } = deckLibrary;
const cameras = new Map();

export default function ({ parentElement, data, setTriggerValue }) {
    const frame = parentElement.querySelector(".map-frame");
    const { region, countries, counties, sites, active, camera } = data;
    const View = region === "World" ? _GlobeView : MapView;
    const polygonStyle = {
        getPolygon: row => row.polygon,
        lineWidthUnits: "pixels",
        wrapLongitude: region === "Alaska",
    };
    const map = new Deck({
        parent: frame,
        views: [new View({ controller: { dragRotate: false, doubleClickZoom: false } })],
        initialViewState: cameras.get(region) ?? camera,
        onViewStateChange: ({ viewState }) => {
            cameras.set(region, viewState);
            return viewState;
        },
        // A software renderer can take longer than the default tap timeout to pick a county.
        eventRecognizerOptions: { click: { time: 5000 } },
        layers: [
            new GeoJsonLayer({
                id: "world-countries", data: countries,
                getFillColor: feature => feature.properties.fill,
                getLineColor: [171, 189, 176], getLineWidth: .5, lineWidthUnits: "pixels",
            }),
            new PolygonLayer({
                ...polygonStyle, id: "counties", data: counties, pickable: true, autoHighlight: true,
                getFillColor: row => row.fill, getLineColor: [120, 152, 170], getLineWidth: .45,
            }),
            new PolygonLayer({
                ...polygonStyle, id: "selected-county", data: counties.filter(row => row.county === active),
                filled: false, getLineColor: [54, 92, 75], getLineWidth: 2,
            }),
            new IconLayer({
                id: "crop-sites", data: sites, pickable: true,
                getPosition: site => site.position, getIcon: site => site.icon,
                getSize: region === "World" ? 20 : 34, sizeUnits: "pixels",
            }),
        ],
        getTooltip: ({ object }) => object?.tooltip ? { text: object.tooltip } : null,
        onClick: ({ object }) => {
            if (object?.county) setTriggerValue("picked", object.county);
        },
    });
    return () => map.finalize();
}
