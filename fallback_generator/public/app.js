import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const scene = new THREE.Scene();
scene.background = new THREE.Color('#1a1a1a');

const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(15, 15, 15);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
scene.add(ambientLight);

const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
dirLight.position.set(10, 20, 10);
dirLight.castShadow = true;
scene.add(dirLight);

const gridHelper = new THREE.GridHelper(50, 50, 0x444444, 0x222222);
scene.add(gridHelper);

window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});

const materialPalette = [
    new THREE.MeshStandardMaterial({ color: 0x4DA8DA, roughness: 0.3, metalness: 0.2 }),
    new THREE.MeshStandardMaterial({ color: 0x007CC7, roughness: 0.3, metalness: 0.2 }),
    new THREE.MeshStandardMaterial({ color: 0xEE4C7C, roughness: 0.3, metalness: 0.2 }),
    new THREE.MeshStandardMaterial({ color: 0xE3AFBC, roughness: 0.3, metalness: 0.2 })
];

let currentMeshes = [];
let drawnLines = [];
let htmlLabels = [];

// ── Shape Inference from Label/ID ─────────────────────────────────────────────
// When Gemini doesn't return resolved_shape (or returns null/undefined),
// we infer the correct shape from the component label using keyword matching.
const SHAPE_KEYWORDS = {
    // IMPORTANT: more-specific entries MUST come before generic ones.
    // e.g. "tetrahedron" before "box" so "triangular face" doesn't fall through to box.
    tetrahedron: [
        'triangular face','triangular_face','triangle face',
        'lateral face','slanting face','sloped face','pyramidal face'
    ],
    cone: [
        'capstone','cap stone','apex','pinnacle','spire','tip','peak',
        'roof','funnel','volcano','spike','cone'
    ],
    hemisphere: [
        'dome','half sphere','cupola','half-sphere'
    ],
    sphere: [
        'sun','star','planet','moon','earth','mars','venus','jupiter','saturn',
        'mercury','uranus','neptune','pluto','nucleus','atom','cell','core',
        'ball','globe','orb','proton','neutron','electron','bubble','droplet',
        'corona','photosphere','solar','layer','zone','mantle','crust','radiative',
        'convective','chromosphere','solar core','inner core','outer core'
    ],
    torus: [
        'ring','orbit','orbital','belt','loop','cycle','asteroid belt',
        'torus','donut','accretion','saturn ring'
    ],
    cylinder: [
        'tube','pipe','channel','stem','trunk','column','pillar','rod',
        'axon','dendrite','vessel','artery','vein','flagella','cilia',
        'tower','minaret','obelisk','dna helix'
    ],
    box: [
        'square base','base','foundation','platform','floor',
        'cube','block','brick','crystal','lattice','grid','square',
        'module','chip','processor','cell wall','chloroplast','wall','side'
    ],
    icosphere: [
        'virus','capsid','geodesic','icosahedron','protein','fullerene','bacteriophage'
    ],
    tapered_cylinder: [
        'rocket','nozzle','taper','horn','megaphone'
    ],
    oblate_sphere: [
        'oblate','flattened','disk','discoid','lenticular','galaxy'
    ]
};

// Stable string hash — same id always gets same palette index (no random blue glitch)
function hashStr(s) {
    let h = 0;
    for (let i = 0; i < (s || '').length; i++) h = Math.imul(31, h) + s.charCodeAt(i) | 0;
    return Math.abs(h) / 2147483648; // normalize to [0,1)
}

function inferShapeFromLabel(label, id) {
    const text = ((label || '') + ' ' + (id || '')).toLowerCase();
    for (const [shape, keywords] of Object.entries(SHAPE_KEYWORDS)) {
        if (keywords.some(kw => text.includes(kw))) {
            return shape;
        }
    }
    return 'sphere'; // scientific default — most natural/astronomical things are spherical
}

// ── Shape Correction ─────────────────────────────────────────────────────────
// Gemini sometimes returns a generic resolved_shape (e.g. "box" for a triangular face).
// This function overrides the server-side resolved_shape when the label clearly
// implies a specific shape — ensuring pyramid faces → tetrahedron, base → box, etc.
const LABEL_OVERRIDES = [
    // Check multi-word patterns FIRST (most specific)
    { keywords: ['triangular face','triangular_face','triangle face','lateral face','slanted face','pyramidal face'], shape: 'tetrahedron' },
    { keywords: ['capstone','cap stone','apex stone','pinnacle','tip stone'],                                         shape: 'cone' },
    { keywords: ['square base','rectangular base','flat base'],                                                       shape: 'box' },
    { keywords: ['dome','cupola','half sphere','half-sphere'],                                                        shape: 'hemisphere' },
    { keywords: ['minaret','tower','obelisk','chimney','mast'],                                                       shape: 'cylinder' },
    // Single-word overrides
    { keywords: ['base','foundation','platform','floor','plinth'],                                                    shape: 'box' },
    { keywords: ['apex','capstone','spire','pinnacle'],                                                               shape: 'cone' },
];

function correctShapeForLabel(resolvedShape, label, id) {
    const text = ((label || '') + ' ' + (id || '')).toLowerCase();
    for (const entry of LABEL_OVERRIDES) {
        if (entry.keywords.some(kw => text.includes(kw))) {
            return entry.shape;
        }
    }
    // If resolved_shape is a valid known shape, trust it
    const validShapes = new Set(['sphere','box','cylinder','cone','torus','hemisphere',
        'icosphere','oblate_sphere','tapered_cylinder','capsule',
        'wireframe_cube','branching_fork','torus_section','octahedron','tetrahedron']);
    if (resolvedShape && validShapes.has(resolvedShape.toLowerCase())) {
        return resolvedShape.toLowerCase();
    }
    return null; // fall through to inferShapeFromLabel
}

// ── Label Deduplication ───────────────────────────────────────────────────────
// Gemini often returns repeated generic labels like "Planets x3", "Moons x3".
// This appends a numeric suffix to make each label unique.
function deduplicateLabels(components) {
    const labelCounts = {};
    const labelSeen = {};
    components.forEach(c => {
        const lbl = (c.label || c.id || 'Component').trim();
        labelCounts[lbl] = (labelCounts[lbl] || 0) + 1;
    });
    return components.map(c => {
        const lbl = (c.label || c.id || 'Component').trim();
        if (labelCounts[lbl] > 1) {
            labelSeen[lbl] = (labelSeen[lbl] || 0) + 1;
            return { ...c, label: `${lbl} ${labelSeen[lbl]}` };
        }
        return c;
    });
}

function createShape(shapeId) {
    shapeId = (shapeId || 'sphere').toLowerCase().trim();

    if (shapeId === 'icosphere') return new THREE.IcosahedronGeometry(0.5, 2);
    if (shapeId === 'torus') return new THREE.TorusGeometry(0.4, 0.15, 16, 32);
    if (shapeId === 'torus_section') return new THREE.TorusGeometry(0.4, 0.15, 16, 32, Math.PI);
    if (shapeId === 'tetrahedron') return new THREE.TetrahedronGeometry(0.5);
    if (shapeId === 'octahedron') return new THREE.OctahedronGeometry(0.5);
    if (shapeId === 'tapered_cylinder') return new THREE.CylinderGeometry(0.2, 0.5, 1, 32);
    if (shapeId === 'capsule') return new THREE.CapsuleGeometry(0.3, 1, 4, 16);

    if (shapeId === 'branching_fork') {
        const group = new THREE.Group();
        const baseGeo = new THREE.CylinderGeometry(0.1, 0.1, 0.6, 16);
        const baseMesh = new THREE.Mesh(baseGeo, new THREE.MeshStandardMaterial({ color: 0xffffff }));
        baseMesh.position.y = -0.2;
        group.add(baseMesh);
        const leftBranch = new THREE.Mesh(baseGeo, new THREE.MeshStandardMaterial({ color: 0xffffff }));
        leftBranch.position.set(-0.2, 0.3, 0);
        leftBranch.rotation.z = Math.PI / 4;
        group.add(leftBranch);
        const rightBranch = new THREE.Mesh(baseGeo, new THREE.MeshStandardMaterial({ color: 0xffffff }));
        rightBranch.position.set(0.2, 0.3, 0);
        rightBranch.rotation.z = -Math.PI / 4;
        group.add(rightBranch);
        group.userData.isPreMeshed = true;
        return group;
    }

    if (shapeId === 'wireframe_cube') {
        const geo = new THREE.BoxGeometry(1, 1, 1);
        const edges = new THREE.EdgesGeometry(geo);
        const line = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({ color: 0xffffff }));
        line.userData.isPreMeshed = true;
        return line;
    }

    if (shapeId === 'oblate_sphere') {
        const geo = new THREE.SphereGeometry(0.5, 32, 16);
        geo.scale(1.4, 0.6, 1.4);
        return geo;
    }
    if (shapeId === 'sphere' || shapeId === 'hemisphere') return new THREE.SphereGeometry(0.5, 32, 16);
    if (shapeId === 'cylinder') return new THREE.CylinderGeometry(0.5, 0.5, 1, 32);
    if (shapeId === 'cone') return new THREE.ConeGeometry(0.5, 1, 32);
    if (shapeId === 'box') return new THREE.BoxGeometry(1, 1, 1);

    console.warn(`[createShape] Unknown shape "${shapeId}", falling back to sphere`);
    return new THREE.SphereGeometry(0.5, 32, 16);
}

function clearScene() {
    currentMeshes.forEach(m => scene.remove(m));
    drawnLines.forEach(l => scene.remove(l));
    htmlLabels.forEach(el => el.element.remove());
    currentMeshes = [];
    drawnLines = [];
    htmlLabels = [];
}

function createHtmlLabel(text, position3D, className) {
    const div = document.createElement('div');
    div.className = className;
    div.innerText = text;
    div.style.position = 'absolute';
    div.style.color = '#fff';
    div.style.backgroundColor = 'rgba(0,0,0,0.6)';
    div.style.padding = '2px 6px';
    div.style.borderRadius = '4px';
    div.style.fontSize = className === 'relation-label' ? '10px' : '12px';
    div.style.pointerEvents = 'none';
    div.style.transform = 'translate(-50%, -50%)';
    document.body.appendChild(div);
    htmlLabels.push({ element: div, pos: position3D });
}

// ── Input Wiring ──────────────────────────────────────────
const input = document.getElementById('concept-input');
const btn = document.getElementById('submit-btn');
const statusEl = document.getElementById('status');

function setStatus(msg, isError = false, isLoading = false) {
    statusEl.className = isError ? 'error' : '';
    statusEl.style.display = 'block';
    if (isLoading) {
        statusEl.innerHTML = `<div class="spinner"></div>${msg}`;
    } else {
        statusEl.innerText = msg;
    }
}

async function submitConcept() {
    const concept = input.value.trim();
    if (!concept) return;

    btn.disabled = true;
    btn.innerText = 'Generating...';
    document.getElementById('ui-layer').style.display = 'none';
    setStatus('Generating 3D visualization...', false, true);

    try {
        const response = await fetch('http://localhost:5000/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ concept })
        });

        const result = await response.json();

        // ── DEBUG: open DevTools (F12) → Console to see this ──────────────────
        console.log('[DEBUG] Full result.data:', result.data);
        if (result.data?.components?.length > 0) {
            console.log('[DEBUG] Shape audit:', result.data.components.map(c => ({
                label: c.label,
                id: c.id,
                resolved_shape: c.resolved_shape,
                shape: c.shape,
                willUse: correctShapeForLabel(c.resolved_shape, c.label, c.id) || inferShapeFromLabel(c.label, c.id)
            })));
        }

        if (!response.ok || result.error) {
            setStatus(`Error: ${result.error}`, true);
        } else {
            statusEl.style.display = 'none';
            renderData(result.data);
        }
    } catch (e) {
        setStatus(`Connection error: ${e.message}`, true);
    } finally {
        btn.disabled = false;
        btn.innerText = 'Visualize';
    }
}

btn.addEventListener('click', submitConcept);
input.addEventListener('keydown', e => { if (e.key === 'Enter') submitConcept(); });

// ── Core Render Function ──────────────────────────────────
function renderData(data) {
    clearScene();

    document.getElementById('ui-layer').style.display = 'block';
    document.getElementById('title').innerText = data.scenario || "Generated Semantic Concept";
    document.getElementById('pattern-badge').innerText = `Graph: ${data.pattern}`;

    const usedVariants = [...new Set((data.components || []).map(c => c.metadata?.variant).filter(v => v && v !== "core"))];
    const vBadge = document.getElementById('variant-badge');
    if (usedVariants.length > 0) {
        vBadge.style.display = 'inline-block';
        vBadge.innerText = `Variant: ${usedVariants.join(' & ')}`;
    } else {
        vBadge.style.display = 'none';
    }

    document.getElementById('desc-intro').innerText =
        (data.intro && data.intro.trim()) ? data.intro : "No visual intro provided.";
    document.getElementById('desc-logic').innerText =
        (data.layout_logic && data.layout_logic.trim()) ? data.layout_logic : "No layout logic provided.";

    // Color palette by morphology family
    let familyPalette = materialPalette;
    const f = data.morphology_family;
    if (f === "nested_membrane")          familyPalette = [0x175c7a, 0x228b99, 0x48b6c4, 0xb8f1fa].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.3 }));
    else if (f === "branching_tree")      familyPalette = [0x507343, 0x25381f, 0xbf9b69, 0x8a5528].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.8 }));
    else if (f === "flow_channel")        familyPalette = [0xcc2929, 0xf0621f, 0xf7a134, 0x821c1c].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.2, metalness: 0.3 }));
    else if (f === "crystalline_lattice") familyPalette = [0xffffff, 0xe0e0e0, 0xb0b0b0, 0x2e86c1].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.1, metalness: 0.8 }));
    else if (f === "field_gradient")      familyPalette = [0x673ab7, 0x9c27b0, 0xe91e63, 0xffc107].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.5 }));
    else if (f === "hub_spoke_web")       familyPalette = [0x00bcd4, 0xb2ebf2, 0xffffff, 0x757575].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.3 }));
    else if (f === "stacked_layers")      familyPalette = [0xe57373, 0x81c784, 0x64b5f6, 0xffd54f, 0xba68c8].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.5 }));
    else if (f === "dense_aggregate")     familyPalette = [0x795548, 0x8d6e63, 0xa1887f, 0xd7ccc8, 0x5d4037].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.9 }));
    else if (f === "helical_chain")       familyPalette = [0xff9800, 0x03a9f4, 0x4caf50, 0xe91e63].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.2 }));
    else if (f === "modular_grid")        familyPalette = [0x263238, 0x37474f, 0x455a64, 0x00e5ff].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.4, metalness: 0.5 }));

    const positionMap = {};

    // Deduplicate labels before rendering (fixes "Planets x3", "Moons x3")
    const components = deduplicateLabels(data.components || []);

    // 1. Plot Geometric Components
    if (data.tube_path && data.tube_path.length > 1) {
        const points = data.tube_path.map(p => new THREE.Vector3(p[0], p[1], p[2]));
        const curve = new THREE.CatmullRomCurve3(points);
        const tubeGeo = new THREE.TubeGeometry(curve, 64, 0.4, 8, false);
        const tubeMat = familyPalette[0].clone();
        tubeMat.transparent = true;
        tubeMat.opacity = 0.85;
        const tubeMesh = new THREE.Mesh(tubeGeo, tubeMat);
        scene.add(tubeMesh);
        currentMeshes.push(tubeMesh);

        components.forEach((comp, idx) => {
            const isContainer = comp.original_component?.metadata?.variant === "container_head";
            const shapeId = correctShapeForLabel(comp.resolved_shape, comp.label, comp.id) || inferShapeFromLabel(comp.label, comp.id);
            const geometry = createShape(shapeId);
            const matIndex = Math.floor(Math.abs(Math.sin(hashStr(comp.original_id || comp.id)) * familyPalette.length));
            const material = familyPalette[matIndex].clone();
            if (isContainer) {
                material.transparent = true;
                material.opacity = 0.4;
                material.side = THREE.DoubleSide;
            }
            const mesh = geometry.userData?.isPreMeshed ? geometry : new THREE.Mesh(geometry, material);
            mesh.position.set(comp.position[0], comp.position[1], comp.position[2]);
            mesh.scale.set(comp.scale[0], comp.scale[1], comp.scale[2]);
            if (!isContainer) mesh.visible = false;
            scene.add(mesh);
            currentMeshes.push(mesh);
            positionMap[comp.original_id || comp.id] = mesh.position.clone();
            createHtmlLabel(comp.label || comp.id, mesh.position.clone().add(new THREE.Vector3(0, comp.scale[1] / 2 + 0.5, 0)), "component-label");
        });

    } else {
        components.forEach((comp, idx) => {
            // Shape resolution: server pipeline → raw shape field → label inference → sphere
            const shapeId = correctShapeForLabel(comp.resolved_shape, comp.label, comp.id) || inferShapeFromLabel(comp.label, comp.id);
            console.log(`[shape] "${comp.label || comp.id}" → using "${shapeId}" (resolved_shape="${comp.resolved_shape}", shape="${comp.shape}")`);

            const geometry = createShape(shapeId);
            const matIndex = Math.floor(Math.abs(Math.sin(hashStr(comp.original_id || comp.id)) * familyPalette.length));
            let material = familyPalette[matIndex].clone();

            if (comp.color_hint === 'parent_dominant') {
                material.color.lerp(new THREE.Color(0xffffff), 0.2);
            } else if (comp.color_hint === 'warning_red') {
                material.color.setHex(0xe62626);
            } else if (comp.color_hint === 'contrast_pair') {
                material.color.setHSL((material.color.getHSL({}).h + 0.5) % 1.0, 0.9, 0.5);
            }

            const mesh = geometry.userData?.isPreMeshed ? geometry : new THREE.Mesh(geometry, material);
            mesh.position.set(comp.position[0], comp.position[1], comp.position[2]);
            mesh.scale.set(comp.scale[0], comp.scale[1], comp.scale[2]);
            scene.add(mesh);
            currentMeshes.push(mesh);
            positionMap[comp.id] = mesh.position.clone();
            createHtmlLabel(comp.label || comp.id, mesh.position.clone().add(new THREE.Vector3(0, comp.scale[1] / 2 + 0.5, 0)), "component-label");
        });
    }

    // 2. Draw Semantic Connectors
    (data.connectors || []).forEach(conn => {
        const startNode = new THREE.Vector3(...conn.start);
        const endNode = new THREE.Vector3(...conn.end);
        const type = conn.type;
        const w = conn.width || 0.1;

        let connColor = 0xffffff;
        if (conn.color_hint === 'warning_red') connColor = 0xe62626;
        else if (conn.color_hint === 'accent_bright') connColor = 0x33cc66;
        else if (conn.color_hint === 'neutral_secondary') connColor = 0x9999a6;
        else if (conn.color_hint === 'gradient_source_to_target') connColor = 0xffaa00;

        if (type === 'tapered_arrow' || type === 'double_arrow_opposing') {
            const dir = new THREE.Vector3().subVectors(endNode, startNode);
            const len = dir.length();
            dir.normalize();
            const bodyGeo = new THREE.CylinderGeometry(w * 0.3, w * 1.5, len * 0.8, 16);
            bodyGeo.translate(0, len * 0.4, 0);
            bodyGeo.rotateX(Math.PI / 2);
            const mesh = new THREE.Mesh(bodyGeo, new THREE.MeshStandardMaterial({ color: connColor }));
            mesh.position.copy(startNode);
            mesh.lookAt(endNode);
            scene.add(mesh);
            drawnLines.push(mesh);
            const headGeo = new THREE.ConeGeometry(w * 2, len * 0.2, 16);
            headGeo.rotateX(Math.PI / 2);
            const head = new THREE.Mesh(headGeo, new THREE.MeshStandardMaterial({ color: connColor }));
            head.position.copy(startNode).add(dir.clone().multiplyScalar(len * 0.9));
            head.lookAt(endNode);
            scene.add(head);
            drawnLines.push(head);

        } else if (type === 'angular_bar') {
            const dir = new THREE.Vector3().subVectors(endNode, startNode).normalize();
            const lineGeo = new THREE.BufferGeometry().setFromPoints([startNode, endNode]);
            const line = new THREE.Line(lineGeo, new THREE.LineBasicMaterial({ color: connColor }));
            scene.add(line);
            drawnLines.push(line);
            const barGeo = new THREE.BoxGeometry(0.5, 0.1, 0.1);
            const bar = new THREE.Mesh(barGeo, new THREE.MeshStandardMaterial({ color: connColor }));
            bar.position.copy(endNode).sub(dir.clone().multiplyScalar(0.2));
            bar.lookAt(endNode);
            scene.add(bar);
            drawnLines.push(bar);

        } else if (type === 'curved_bidirectional') {
            if (conn.control_points && conn.control_points.length > 0) {
                const cp = new THREE.Vector3(...conn.control_points[0]);
                const curve = new THREE.QuadraticBezierCurve3(startNode, cp, endNode);
                const tubeGeo = new THREE.TubeGeometry(curve, 20, w, 8, false);
                const tube = new THREE.Mesh(tubeGeo, new THREE.MeshStandardMaterial({ color: connColor }));
                scene.add(tube);
                drawnLines.push(tube);
            }

        } else if (type === 'dashed_equal') {
            const dir = new THREE.Vector3().subVectors(endNode, startNode);
            const dist = dir.length();
            dir.normalize();
            const segments = 5;
            const step = dist / (segments * 2);
            for (let i = 0; i < segments; i++) {
                const p1 = startNode.clone().add(dir.clone().multiplyScalar(i * 2 * step));
                const p2 = startNode.clone().add(dir.clone().multiplyScalar((i * 2 + 1) * step));
                const lGeo = new THREE.BufferGeometry().setFromPoints([p1, p2]);
                const l = new THREE.Line(lGeo, new THREE.LineBasicMaterial({ color: connColor }));
                scene.add(l);
                drawnLines.push(l);
            }

        } else {
            const points = [startNode, endNode];
            const geometry = new THREE.BufferGeometry().setFromPoints(points);
            const lMat = new THREE.LineBasicMaterial({ color: connColor, opacity: 0.5, transparent: true });
            const line = new THREE.Line(geometry, lMat);
            scene.add(line);
            drawnLines.push(line);
        }
    });

    // 3. Floating Contextual Annotations
    (data.contextual_annotations || []).forEach(ann => {
        const targetNode = positionMap[ann.target];
        if (targetNode) {
            createHtmlLabel(ann.text, targetNode.clone().add(new THREE.Vector3(2, 2, 0)), "annotation-label");
        }
    });
}

function updateLabels() {
    htmlLabels.forEach(lblObj => {
        const vector = lblObj.pos.clone();
        vector.project(camera);
        const x = (vector.x * .5 + .5) * window.innerWidth;
        const y = (vector.y * -.5 + .5) * window.innerHeight;
        lblObj.element.style.left = `${x}px`;
        lblObj.element.style.top = `${y}px`;
        if (vector.z > 1) lblObj.element.style.display = 'none';
        else lblObj.element.style.display = 'block';
    });
}

function animate() {
    requestAnimationFrame(animate);
    controls.update();
    updateLabels();
    renderer.render(scene, camera);
}
animate();