const { Deck, GeoJsonLayer, PolygonLayer, IconLayer, MapView, _GlobeView } = deckLibrary;
const cameras = new Map();

export default function ({ parentElement, data, setTriggerValue }) {
    const frame = parentElement.querySelector(".map-frame");
    const { region, countries, counties, sites, active, camera, siteZoom } = data;
    const View = region === "World" ? _GlobeView : MapView;
    const pinSize = region === "World" ? 20 : 34;
    let hoveringPin = false;
    let pinFlight;
    const polygonStyle = {
        getPolygon: row => row.polygon,
        lineWidthUnits: "pixels",
        wrapLongitude: region === "Alaska",
    };
    const map = new Deck({
        parent: frame,
        views: [new View({ controller: { dragRotate: false, doubleClickZoom: false } })],
        viewState: cameras.get(region) ?? camera,
        onViewStateChange: ({ viewState }) => {
            setCamera(viewState);
            const county = stopPinFlight();
            if (county) setTriggerValue("picked", county);
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
                getSize: site => site.county === active ? pinSize * 1.35 : pinSize,
                sizeUnits: "pixels",
            }),
        ],
        getTooltip: ({ object }) => object?.tooltip ? { text: object.tooltip } : null,
        onHover: ({ layer, picked }) => {
            hoveringPin = picked && layer?.id === "crop-sites";
        },
        getCursor: ({ isDragging }) => {
            if (isDragging) return "grabbing";
            return hoveringPin ? "pointer" : "grab";
        },
        onClick: ({ layer, object }) => {
            if (!object?.county) return;
            stopPinFlight();
            if (layer?.id === "crop-sites") focusSite(object);
            else setTriggerValue("picked", object.county);
        },
    });

    function focusSite({ position: [longitude, latitude], county }) {
        const current = cameras.get(region) ?? camera;
        const zoom = Math.max(current.zoom, siteZoom);
        const delta = longitude - current.longitude;
        const longitudeDelta = delta - 360 * Math.round(delta / 360);
        const target = { ...current, longitude: current.longitude + longitudeDelta, latitude, zoom };
        if (longitudeDelta === 0 && current.latitude === latitude && current.zoom === zoom) {
            setCamera(target);
            setTriggerValue("picked", county);
            return;
        }

        let start;
        function animate(now) {
            start ??= now;
            const progress = Math.min((now - start) / 1600, 1);
            const t = progress * progress * (3 - 2 * progress);
            if (progress < 1) {
                // Lead with the pan so the pin stays in view as the map grows.
                const pan = t * (2 - t);
                setCamera({
                    ...current,
                    longitude: current.longitude + longitudeDelta * pan,
                    latitude: current.latitude + (latitude - current.latitude) * pan,
                    zoom: current.zoom + (zoom - current.zoom) * t,
                });
                pinFlight.frame = requestAnimationFrame(animate);
            } else {
                pinFlight = null;
                setCamera(target);
                // Selecting the county reruns Streamlit. Let the camera arrive first.
                setTriggerValue("picked", county);
            }
        }
        pinFlight = { county, frame: requestAnimationFrame(animate) };
    }

    function stopPinFlight() {
        if (!pinFlight) return;
        cancelAnimationFrame(pinFlight.frame);
        const { county } = pinFlight;
        pinFlight = null;
        return county;
    }

    function setCamera(viewState) {
        // Keep the camera position when Streamlit reruns after a selection.
        cameras.set(region, viewState);
        map.setProps({ viewState });
    }

    return () => {
        stopPinFlight();
        map.finalize();
    };
}
