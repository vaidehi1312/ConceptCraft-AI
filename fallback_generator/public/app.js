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

function createShape(shapeId) {
    shapeId = (shapeId || 'box').toLowerCase();

    // 1. Core Primitives
    if (shapeId === 'icosphere') return new THREE.IcosahedronGeometry(0.5, 2);
    if (shapeId === 'torus') return new THREE.TorusGeometry(0.4, 0.15, 16, 32);
    if (shapeId === 'torus_section') return new THREE.TorusGeometry(0.4, 0.15, 16, 32, Math.PI);
    if (shapeId === 'tetrahedron') return new THREE.TetrahedronGeometry(0.5);
    if (shapeId === 'octahedron') return new THREE.OctahedronGeometry(0.5);
    if (shapeId === 'tapered_cylinder') return new THREE.CylinderGeometry(0.2, 0.5, 1, 32);
    if (shapeId === 'capsule') return new THREE.CapsuleGeometry(0.3, 1, 4, 16);

    // 2. Complex Group Fakes (We return a group instead of raw geometry for complex shapes)
    if (shapeId === 'branching_fork') {
        const group = new THREE.Group();

        // Base stem
        const baseGeo = new THREE.CylinderGeometry(0.1, 0.1, 0.6, 16);
        const baseMesh = new THREE.Mesh(baseGeo, new THREE.MeshStandardMaterial({ color: 0xffffff }));
        baseMesh.position.y = -0.2;
        group.add(baseMesh);

        // Left branch
        const leftBranch = new THREE.Mesh(baseGeo, new THREE.MeshStandardMaterial({ color: 0xffffff }));
        leftBranch.position.set(-0.2, 0.3, 0);
        leftBranch.rotation.z = Math.PI / 4;
        group.add(leftBranch);

        // Right branch
        const rightBranch = new THREE.Mesh(baseGeo, new THREE.MeshStandardMaterial({ color: 0xffffff }));
        rightBranch.position.set(0.2, 0.3, 0);
        rightBranch.rotation.z = -Math.PI / 4;
        group.add(rightBranch);

        // Set a flag so the main loop knows it's already meshed
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

    // 3. Defaults & Modifiers
    if (shapeId === 'oblate_sphere') {
        const geo = new THREE.SphereGeometry(0.5, 32, 16);
        // Scaling handled by the component's scale vector later, but we could pre-scale the geometry here:
        geo.scale(1.4, 0.6, 1.4);
        return geo;
    }
    if (shapeId === 'sphere' || shapeId === 'hemisphere') return new THREE.SphereGeometry(0.5, 32, 16);
    if (shapeId === 'cylinder') return new THREE.CylinderGeometry(0.5, 0.5, 1, 32);
    if (shapeId === 'cone') return new THREE.ConeGeometry(0.5, 1, 32);
    if (shapeId === 'box') return new THREE.BoxGeometry(1, 1, 1);

    return new THREE.SphereGeometry(0.5, 32, 16); // Ultimate fallback
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
    div.style.transform = 'translate(-50%, -50%)'; // Center pivot
    document.body.appendChild(div);
    htmlLabels.push({ element: div, pos: position3D });
}

let lastFetchedData = null;

async function pollData() {
    try {
        const response = await fetch('output.json?t=' + new Date().getTime());
        if (!response.ok) return;
        const data = await response.json();

        if (lastFetchedData === JSON.stringify(data)) return;
        lastFetchedData = JSON.stringify(data);

        clearScene();

        document.getElementById('loading').style.display = 'none';
        document.getElementById('ui-layer').style.display = 'block';
        document.getElementById('title').innerText = data.scenario || "Generated Semantic Concept";
        document.getElementById('pattern-badge').innerText = `Graph: ${data.pattern}`;

        // Extract unique variants used in the output graph
        const usedVariants = [...new Set((data.components || []).map(c => c.metadata && c.metadata.variant).filter(v => v && v !== "core"))];
        const vBadge = document.getElementById('variant-badge');
        if (usedVariants.length > 0) {
            vBadge.style.display = 'inline-block';
            vBadge.innerText = `Variant: ${usedVariants.join(' & ')}`;
        } else {
            vBadge.style.display = 'none';
        }

        document.getElementById('desc-intro').innerText = data.intro || "No visual intro provided.";
        document.getElementById('desc-logic').innerText = data.layout_logic || "No layout logic provided.";

        // Base Color Palette Setup based on morphology_family
        let familyPalette = materialPalette; // Default fallback
        const f = data.morphology_family;
        if (f === "nested_membrane") familyPalette = [0x175c7a, 0x228b99, 0x48b6c4, 0xb8f1fa].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.3 }));
        else if (f === "branching_tree") familyPalette = [0x507343, 0x25381f, 0xbf9b69, 0x8a5528].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.8 }));
        else if (f === "flow_channel") familyPalette = [0xcc2929, 0xf0621f, 0xf7a134, 0x821c1c].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.2, metalness: 0.3 }));
        else if (f === "crystalline_lattice") familyPalette = [0xffffff, 0xe0e0e0, 0xb0b0b0, 0x2e86c1].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.1, metalness: 0.8 }));
        else if (f === "field_gradient") familyPalette = [0x673ab7, 0x9c27b0, 0xe91e63, 0xffc107].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.5 }));
        else if (f === "hub_spoke_web") familyPalette = [0x00bcd4, 0xb2ebf2, 0xffffff, 0x757575].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.3 }));
        else if (f === "stacked_layers") familyPalette = [0xe57373, 0x81c784, 0x64b5f6, 0xffd54f, 0xba68c8].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.5 }));
        else if (f === "dense_aggregate") familyPalette = [0x795548, 0x8d6e63, 0xa1887f, 0xd7ccc8, 0x5d4037].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.9 }));
        else if (f === "helical_chain") familyPalette = [0xff9800, 0x03a9f4, 0x4caf50, 0xe91e63].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.2 }));
        else if (f === "modular_grid") familyPalette = [0x263238, 0x37474f, 0x455a64, 0x00e5ff].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.4, metalness: 0.5 }));

        const positionMap = {};

        // 1. Plot Geometric Components & Build Map
        if (data.tube_path && data.tube_path.length > 1) {
            // Build continuous tube
            const points = data.tube_path.map(p => new THREE.Vector3(p[0], p[1], p[2]));
            // Use catmull-rom for smooth curve interpolation
            const curve = new THREE.CatmullRomCurve3(points);
            const tubeRadius = 0.4;
            const tubeGeo = new THREE.TubeGeometry(curve, 64, tubeRadius, 8, false);
            const tubeMat = familyPalette[0].clone();
            tubeMat.transparent = true;
            tubeMat.opacity = 0.85;
            const tubeMesh = new THREE.Mesh(tubeGeo, tubeMat);
            scene.add(tubeMesh);
            currentMeshes.push(tubeMesh);

            data.components.forEach((comp, idx) => {
                // Keep the container head (e.g. Bowman's Capsule) visible as the outer shell
                const isContainer = comp.original_component && comp.original_component.metadata && comp.original_component.metadata.variant === "container_head";

                const geometry = createShape(comp.resolved_shape);
                const matIndex = Math.floor(Math.abs(Math.sin((comp.original_id || comp.id).length + idx) * familyPalette.length));
                // Set the container shell to be semi-transparent
                const material = familyPalette[matIndex].clone();
                if (isContainer) {
                    material.transparent = true;
                    material.opacity = 0.4;
                    material.side = THREE.DoubleSide; // Ensure shell is visible from inside out
                }

                const mesh = geometry.userData && geometry.userData.isPreMeshed ? geometry : new THREE.Mesh(geometry, material);
                mesh.position.set(comp.position[0], comp.position[1], comp.position[2]);
                mesh.scale.set(comp.scale[0], comp.scale[1], comp.scale[2]); // Pre-scaled logically

                if (!isContainer) {
                    // Make it invisible but keep it for label positioning
                    mesh.visible = false;
                }

                scene.add(mesh);
                currentMeshes.push(mesh);
                positionMap[comp.original_id || comp.id] = mesh.position.clone();
                createHtmlLabel(comp.label || comp.id, mesh.position.clone().add(new THREE.Vector3(0, comp.scale[1] / 2 + 0.5, 0)), "component-label");
            });

        } else {
            (data.components || []).forEach((comp, idx) => {
                const geometry = createShape(comp.resolved_shape);
                const matIndex = Math.floor(Math.abs(Math.sin((comp.original_id || comp.id).length + idx) * familyPalette.length));

                let material = familyPalette[matIndex].clone();

                // Specifically map color hints onto materials
                if (comp.color_hint === 'parent_dominant') {
                    // Try to simulate dominance with first palette logic or bright state
                    material.color.lerp(new THREE.Color(0xffffff), 0.2);
                } else if (comp.color_hint === 'warning_red') {
                    material.color.setHex(0xe62626);
                } else if (comp.color_hint === 'contrast_pair') {
                    // Simple simulated inversion
                    material.color.setHSL((material.color.getHSL({}).h + 0.5) % 1.0, 0.9, 0.5);
                }

                const mesh = geometry.userData && geometry.userData.isPreMeshed ? geometry : new THREE.Mesh(geometry, material);
                mesh.position.set(comp.position[0], comp.position[1], comp.position[2]);
                mesh.scale.set(comp.scale[0], comp.scale[1], comp.scale[2]);
                scene.add(mesh);
                currentMeshes.push(mesh);

                // Core original ID maps back to its primary coordinate vector
                positionMap[comp.id] = mesh.position.clone();

                // Label directly above mesh
                createHtmlLabel(comp.label || comp.id, mesh.position.clone().add(new THREE.Vector3(0, comp.scale[1] / 2 + 0.5, 0)), "component-label");
            });
        }

        // 2. Draw Semantic Connectors via rel geometry metadata
        const lineMat = new THREE.LineBasicMaterial({ color: 0xffffff, opacity: 0.5, transparent: true });

        (data.connectors || []).forEach(conn => {
            const startNode = new THREE.Vector3(...conn.start);
            const endNode = new THREE.Vector3(...conn.end);

            const shape = conn.shape; // tapered_arrow abstracted down to primitive shape specs usually in morphology_bridge, or use conn.type
            const type = conn.type;
            const w = conn.width || 0.1;

            // Map color hints
            let connColor = 0xffffff;
            if (conn.color_hint === 'warning_red') connColor = 0xe62626;
            else if (conn.color_hint === 'accent_bright') connColor = 0x33cc66;
            else if (conn.color_hint === 'neutral_secondary') connColor = 0x9999a6;
            else if (conn.color_hint === 'gradient_source_to_target') connColor = 0xffaa00; // Mocked gradient

            if (type === 'tapered_arrow' || type === 'double_arrow_opposing') {
                // Direction vector
                const dir = new THREE.Vector3().subVectors(endNode, startNode);
                const len = dir.length();
                dir.normalize();

                // Cylinder body
                const bodyGeo = new THREE.CylinderGeometry(w * 0.3, w * 1.5, len * 0.8, 16);
                bodyGeo.translate(0, len * 0.4, 0);
                bodyGeo.rotateX(Math.PI / 2);

                const mesh = new THREE.Mesh(bodyGeo, new THREE.MeshStandardMaterial({ color: connColor }));
                mesh.position.copy(startNode);
                mesh.lookAt(endNode);
                scene.add(mesh);
                drawnLines.push(mesh);

                // Arrowhead
                const headGeo = new THREE.ConeGeometry(w * 2, len * 0.2, 16);
                headGeo.rotateX(Math.PI / 2);
                const head = new THREE.Mesh(headGeo, new THREE.MeshStandardMaterial({ color: connColor }));
                head.position.copy(startNode).add(dir.clone().multiplyScalar(len * 0.9));
                head.lookAt(endNode);
                scene.add(head);
                drawnLines.push(head);

            } else if (type === 'angular_bar') {
                const mid = new THREE.Vector3().addVectors(startNode, endNode).multiplyScalar(0.5);
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
                // Fallback thin_line
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

    } catch (e) { console.error('[ConceptCraftAI] Render error:', e); }
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

setInterval(pollData, 1000);

function animate() {
    requestAnimationFrame(animate);
    controls.update();
    updateLabels();
    renderer.render(scene, camera);
}
animate();
