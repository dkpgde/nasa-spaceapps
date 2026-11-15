const { Deck, GeoJsonLayer, PolygonLayer, IconLayer, TileLayer, BitmapLayer, MapView, _GlobeView } = deckLibrary;
const cameras = new Map();
let displayedSearch = 0;

export default function ({ parentElement, data, setTriggerValue }) {
    const frame = parentElement.querySelector(".map-frame");
    const controls = parentElement.querySelector(".map-controls");
    const status = parentElement.querySelector(".map-status");
    const attribution = parentElement.querySelector(".map-attribution");
    const { region, countries, counties, sites, active, camera, siteZoom, imagery, search, revision } = data;
    const visibleSites = search ? sites.filter(({ position }) => (
        Math.hypot(position[0] - search.position[0], position[1] - search.position[1]) > .0003
    )) : sites;
    const remembered = cameras.get(region);
    if (remembered?.revision !== revision) cameras.set(region, { revision, viewState: camera });
    const View = region === "World" ? _GlobeView : MapView;
    const pinSize = region === "World" ? 20 : 34;
    let hoveringPin = false;
    let pinFlight;
    let imageryReady = false;
    attribution.hidden = !imagery;
    frame.dataset.imagery = imagery ? "loading" : "off";
    status.hidden = !imagery;
    status.textContent = imagery ? "Loading satellite imagery…" : "";
    const polygonStyle = {
        getPolygon: row => row.polygon,
        lineWidthUnits: "pixels",
        wrapLongitude: region === "Alaska",
    };
    const basemap = imagery && new TileLayer({
        id: "satellite-imagery", data: imagery,
        minZoom: 0, maxZoom: 19, tileSize: 256,
        onTileLoad: tile => {
            if (!tile.content) return;
            imageryReady = true;
            frame.dataset.imagery = "ready";
            status.hidden = true;
        },
        onTileError: () => {
            if (imageryReady) return;
            frame.dataset.imagery = "unavailable";
            status.textContent = "Satellite imagery is unavailable. Weather coverage works offline.";
            status.hidden = false;
        },
        renderSubLayers: props => {
            const { west, south, east, north } = props.tile.bbox;
            return new BitmapLayer(props, {
                data: null, image: props.data, bounds: [west, south, east, north],
            });
        },
    });
    const map = new Deck({
        parent: frame,
        views: [new View({ repeat: Boolean(imagery), controller: { dragRotate: false, doubleClickZoom: true } })],
        viewState: cameras.get(region).viewState,
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
            basemap,
            new PolygonLayer({
                ...polygonStyle, id: "counties", data: counties, pickable: true, autoHighlight: true,
                getFillColor: row => imagery ? [0, 0, 0, 0] : row.fill,
                getLineColor: imagery ? [222, 240, 228, 105] : [120, 152, 170], getLineWidth: .45,
            }),
            new PolygonLayer({
                ...polygonStyle, id: "selected-county", data: counties.filter(row => row.county === active),
                filled: false, getLineColor: imagery ? [226, 243, 218, 180] : [54, 92, 75], getLineWidth: 2,
            }),
            new IconLayer({
                id: "crop-sites", data: visibleSites, pickable: true,
                getPosition: site => site.position, getIcon: site => site.icon,
                getSize: site => site.county === active ? pinSize * 1.35 : pinSize,
                sizeUnits: "pixels",
            }),
            search && new IconLayer({
                id: "search-result", data: [search], pickable: true,
                getPosition: point => point.position, getIcon: point => point.icon,
                getSize: 39, sizeUnits: "pixels",
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
        const current = cameras.get(region).viewState;
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
        cameras.set(region, { revision, viewState });
        map.setProps({ viewState });
    }

    function useControl(event) {
        const zoom = event.target.dataset.zoom;
        if (zoom === undefined && !event.target.hasAttribute("data-recenter")) return;
        const county = stopPinFlight();
        const current = cameras.get(region).viewState;
        const target = zoom === undefined ? camera : {
            ...current,
            zoom: Math.max(camera.minZoom, Math.min(camera.maxZoom, current.zoom + Number(zoom))),
        };
        setCamera(target);
        if (county) setTriggerValue("picked", county);
    }
    controls.addEventListener("click", useControl);
    let revealFrame;
    if (search && revision > displayedSearch) {
        displayedSearch = revision;
        revealFrame = requestAnimationFrame(() => frame.scrollIntoView({ block: "center", behavior: "smooth" }));
    }

    return () => {
        if (revealFrame) cancelAnimationFrame(revealFrame);
        controls.removeEventListener("click", useControl);
        stopPinFlight();
        map.finalize();
    };
}
