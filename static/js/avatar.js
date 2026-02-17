/**
 * avatar.js — Three.js Procedural Avatar for AI Tutor
 * Creates a stylized humanoid character with:
 *   - Eyebrows (rotatable for expressions)
 *   - Eyelids (squint/widen for emotions)
 *   - Improved mouth geometry (Shape-based)
 *   - 6 gesture animations: idle, talk, nod, wave, think, celebrate, point, shrug
 *   - 5 expression presets: happy, serious, encouraging, confused, excited
 *   - Emotion-driven platform glow colors
 */

(function () {
    'use strict';

    // ═══════════════════════════════════════════════
    // STATE
    // ═══════════════════════════════════════════════
    const STATE = {
        scene: null,
        camera: null,
        renderer: null,
        clock: null,
        avatar: null,
        // Head parts
        head: null,
        mouth: null,
        leftEye: null,
        rightEye: null,
        leftEyebrow: null,
        rightEyebrow: null,
        leftEyelid: null,
        rightEyelid: null,
        // Body parts
        body: null,
        leftArm: null,
        rightArm: null,
        leftHand: null,
        rightHand: null,
        // Platform
        glowRing: null,
        platformLight: null,
        // Animation state
        currentEmotion: 'neutral',
        currentGesture: 'idle',
        gestureTimer: 0,
        mouthOpenAmount: 0,
        targetMouthOpen: 0,
        headRotX: 0,
        headRotY: 0,
        targetHeadRotX: 0,
        targetHeadRotY: 0,
        // Expression targets (smoothly interpolated)
        expression: {
            eyebrowLeftAngle: 0,     // radians, positive = raised
            eyebrowRightAngle: 0,
            eyebrowLeftY: 0,         // vertical offset
            eyebrowRightY: 0,
            eyelidLeft: 1,           // 1 = fully open, 0 = fully closed
            eyelidRight: 1,
            mouthWidth: 1,           // 1 = normal, >1 = smile, <1 = purse
        },
        expressionTarget: {
            eyebrowLeftAngle: 0,
            eyebrowRightAngle: 0,
            eyebrowLeftY: 0,
            eyebrowRightY: 0,
            eyelidLeft: 1,
            eyelidRight: 1,
            mouthWidth: 1,
        },
        // Particles
        particleSystem: null,
        ambientParticles: [],
        isInitialized: false,
        isTalking: false,
        talkStartTime: 0
    };

    // ═══════════════════════════════════════════════
    // COLORS
    // ═══════════════════════════════════════════════
    const COLORS = {
        skin: 0x8B6F5C,
        skinLight: 0xA08070,
        hair: 0x2A1B0F,
        shirt: 0x3B82F6,
        shirtAccent: 0x2563EB,
        pants: 0x1E293B,
        eyeWhite: 0xF0F0F0,
        eyeIris: 0x2D5F8A,
        eyePupil: 0x111111,
        eyebrow: 0x1A0E05,
        eyelid: 0x7A6050,
        mouthDefault: 0xCC5544,
        mouthOpen: 0x8B3333,
        platform: 0x1E293B,
        glowPrimary: 0x60A5FA,
        glowSecondary: 0xA78BFA,
        ambient: 0x0a0e1a
    };

    // Emotion → glow color mapping
    const EMOTION_GLOW = {
        happy: 0x34D399,
        serious: 0xF59E0B,
        encouraging: 0x60A5FA,
        confused: 0xF472B6,
        excited: 0xA78BFA,
        neutral: 0x60A5FA
    };

    // Expression presets: define target values for each emotion
    const EXPRESSION_PRESETS = {
        happy: {
            eyebrowLeftAngle: 0.15, eyebrowRightAngle: 0.15,
            eyebrowLeftY: 0.02, eyebrowRightY: 0.02,
            eyelidLeft: 0.75, eyelidRight: 0.75,   // gentle squint (smile)
            mouthWidth: 1.3
        },
        serious: {
            eyebrowLeftAngle: -0.12, eyebrowRightAngle: -0.12,
            eyebrowLeftY: -0.01, eyebrowRightY: -0.01,
            eyelidLeft: 0.85, eyelidRight: 0.85,
            mouthWidth: 0.85
        },
        encouraging: {
            eyebrowLeftAngle: 0.12, eyebrowRightAngle: 0.12,
            eyebrowLeftY: 0.015, eyebrowRightY: 0.015,
            eyelidLeft: 0.8, eyelidRight: 0.8,      // warm squint
            mouthWidth: 1.15
        },
        confused: {
            eyebrowLeftAngle: 0.2, eyebrowRightAngle: -0.15,  // one up, one down
            eyebrowLeftY: 0.025, eyebrowRightY: -0.005,
            eyelidLeft: 1.0, eyelidRight: 0.8,
            mouthWidth: 0.9
        },
        excited: {
            eyebrowLeftAngle: 0.25, eyebrowRightAngle: 0.25,
            eyebrowLeftY: 0.03, eyebrowRightY: 0.03,
            eyelidLeft: 1.1, eyelidRight: 1.1,       // wide eyes
            mouthWidth: 1.35
        },
        neutral: {
            eyebrowLeftAngle: 0, eyebrowRightAngle: 0,
            eyebrowLeftY: 0, eyebrowRightY: 0,
            eyelidLeft: 1, eyelidRight: 1,
            mouthWidth: 1
        }
    };

    // ═══════════════════════════════════════════════
    // INIT
    // ═══════════════════════════════════════════════
    function init() {
        const canvas = document.getElementById('avatarCanvas');
        if (!canvas) return;

        STATE.clock = new THREE.Clock();

        // Scene
        STATE.scene = new THREE.Scene();
        STATE.scene.background = new THREE.Color(COLORS.ambient);
        STATE.scene.fog = new THREE.FogExp2(COLORS.ambient, 0.015);

        // Camera
        STATE.camera = new THREE.PerspectiveCamera(35, canvas.clientWidth / canvas.clientHeight, 0.1, 100);
        STATE.camera.position.set(0, 1.8, 5);
        STATE.camera.lookAt(0, 1.2, 0);

        // Renderer
        STATE.renderer = new THREE.WebGLRenderer({
            canvas: canvas,
            antialias: true,
            alpha: false
        });
        STATE.renderer.setSize(canvas.clientWidth, canvas.clientHeight);
        STATE.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        STATE.renderer.shadowMap.enabled = true;
        STATE.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        STATE.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        STATE.renderer.toneMappingExposure = 1.2;

        // Lighting
        setupLighting();

        // Build Avatar
        buildAvatar();

        // Platform & Particles
        createPlatform();
        createAmbientParticles();

        // Handle resize
        window.addEventListener('resize', onResize);
        onResize();

        STATE.isInitialized = true;

        // Start render loop
        animate();
    }

    // ═══════════════════════════════════════════════
    // LIGHTING
    // ═══════════════════════════════════════════════
    function setupLighting() {
        // Ambient
        const ambient = new THREE.AmbientLight(0x404050, 0.6);
        STATE.scene.add(ambient);

        // Main key light
        const keyLight = new THREE.DirectionalLight(0xFFE4CC, 1.2);
        keyLight.position.set(3, 5, 4);
        keyLight.castShadow = true;
        keyLight.shadow.mapSize.width = 1024;
        keyLight.shadow.mapSize.height = 1024;
        STATE.scene.add(keyLight);

        // Fill light (blue tint)
        const fillLight = new THREE.DirectionalLight(0x6090FF, 0.4);
        fillLight.position.set(-3, 3, -2);
        STATE.scene.add(fillLight);

        // Rim light
        const rimLight = new THREE.DirectionalLight(0xA78BFA, 0.5);
        rimLight.position.set(0, 2, -5);
        STATE.scene.add(rimLight);

        // Ground bounce (emotion-driven)
        STATE.platformLight = new THREE.PointLight(COLORS.glowPrimary, 0.3, 10);
        STATE.platformLight.position.set(0, 0.2, 1);
        STATE.scene.add(STATE.platformLight);
    }

    // ═══════════════════════════════════════════════
    // BUILD AVATAR
    // ═══════════════════════════════════════════════
    function buildAvatar() {
        STATE.avatar = new THREE.Group();

        // ── BODY (torso) ──
        const bodyGeo = new THREE.CylinderGeometry(0.32, 0.28, 0.8, 12);
        const bodyMat = new THREE.MeshStandardMaterial({
            color: COLORS.shirt,
            roughness: 0.5,
            metalness: 0.1
        });
        STATE.body = new THREE.Mesh(bodyGeo, bodyMat);
        STATE.body.position.y = 1.1;
        STATE.body.castShadow = true;
        STATE.avatar.add(STATE.body);

        // Shirt collar accent
        const collarGeo = new THREE.TorusGeometry(0.3, 0.03, 8, 12, Math.PI);
        const collarMat = new THREE.MeshStandardMaterial({ color: COLORS.shirtAccent, roughness: 0.4 });
        const collar = new THREE.Mesh(collarGeo, collarMat);
        collar.position.set(0, 0.38, 0.1);
        collar.rotation.x = -0.3;
        STATE.body.add(collar);

        // ── HEAD ──
        STATE.head = new THREE.Group();
        STATE.head.position.y = 1.75;

        // Head sphere
        const headGeo = new THREE.SphereGeometry(0.28, 16, 16);
        const headMat = new THREE.MeshStandardMaterial({
            color: COLORS.skin,
            roughness: 0.6,
            metalness: 0.05
        });
        const headMesh = new THREE.Mesh(headGeo, headMat);
        headMesh.castShadow = true;
        STATE.head.add(headMesh);

        // Hair
        const hairGeo = new THREE.SphereGeometry(0.30, 16, 16, 0, Math.PI * 2, 0, Math.PI * 0.55);
        const hairMat = new THREE.MeshStandardMaterial({
            color: COLORS.hair,
            roughness: 0.8,
            metalness: 0.05
        });
        const hair = new THREE.Mesh(hairGeo, hairMat);
        hair.position.y = 0.02;
        hair.rotation.x = -0.1;
        STATE.head.add(hair);

        // ── EYES ──
        buildEyes();

        // ── EYEBROWS ──
        buildEyebrows();

        // ── EYELIDS ──
        buildEyelids();

        // ── MOUTH ──
        buildMouth();

        // Nose
        const noseGeo = new THREE.ConeGeometry(0.03, 0.06, 6);
        const noseMat = new THREE.MeshStandardMaterial({ color: COLORS.skinLight, roughness: 0.6 });
        const nose = new THREE.Mesh(noseGeo, noseMat);
        nose.position.set(0, 0, 0.26);
        nose.rotation.x = -Math.PI / 2;
        STATE.head.add(nose);

        // Neck
        const neckGeo = new THREE.CylinderGeometry(0.08, 0.1, 0.15, 8);
        const neckMat = new THREE.MeshStandardMaterial({ color: COLORS.skin, roughness: 0.6 });
        const neck = new THREE.Mesh(neckGeo, neckMat);
        neck.position.y = -0.35;
        STATE.head.add(neck);

        STATE.avatar.add(STATE.head);

        // ── ARMS ──
        buildArms();

        // ── LEGS ──
        buildLegs();

        STATE.scene.add(STATE.avatar);
    }

    // ── EYE BUILD ──
    function buildEyes() {
        const eyeGeo = new THREE.SphereGeometry(0.05, 8, 8);
        const eyeWhiteMat = new THREE.MeshStandardMaterial({ color: COLORS.eyeWhite, roughness: 0.2 });

        STATE.leftEye = new THREE.Group();
        const leftEyeWhite = new THREE.Mesh(eyeGeo, eyeWhiteMat);
        STATE.leftEye.add(leftEyeWhite);
        const irisGeo = new THREE.SphereGeometry(0.028, 8, 8);
        const irisMat = new THREE.MeshStandardMaterial({ color: COLORS.eyeIris, roughness: 0.3 });
        const leftIris = new THREE.Mesh(irisGeo, irisMat);
        leftIris.position.z = 0.035;
        STATE.leftEye.add(leftIris);
        const pupilGeo = new THREE.SphereGeometry(0.015, 8, 8);
        const pupilMat = new THREE.MeshStandardMaterial({ color: COLORS.eyePupil, roughness: 0.1 });
        const leftPupil = new THREE.Mesh(pupilGeo, pupilMat);
        leftPupil.position.z = 0.045;
        STATE.leftEye.add(leftPupil);
        STATE.leftEye.position.set(-0.1, 0.04, 0.22);
        STATE.head.add(STATE.leftEye);

        STATE.rightEye = STATE.leftEye.clone();
        STATE.rightEye.position.set(0.1, 0.04, 0.22);
        STATE.head.add(STATE.rightEye);
    }

    // ── EYEBROW BUILD ──
    function buildEyebrows() {
        const browGeo = new THREE.BoxGeometry(0.08, 0.012, 0.02);
        const browMat = new THREE.MeshStandardMaterial({
            color: COLORS.eyebrow,
            roughness: 0.7
        });

        // Left eyebrow
        STATE.leftEyebrow = new THREE.Mesh(browGeo, browMat);
        STATE.leftEyebrow.position.set(-0.1, 0.11, 0.24);
        STATE.head.add(STATE.leftEyebrow);

        // Right eyebrow
        STATE.rightEyebrow = new THREE.Mesh(browGeo.clone(), browMat.clone());
        STATE.rightEyebrow.position.set(0.1, 0.11, 0.24);
        STATE.head.add(STATE.rightEyebrow);
    }

    // ── EYELID BUILD ──
    function buildEyelids() {
        // Eyelids are thin slabs that sit above each eye, scaling down to "close"
        const lidGeo = new THREE.BoxGeometry(0.11, 0.015, 0.04);
        const lidMat = new THREE.MeshStandardMaterial({
            color: COLORS.eyelid,
            roughness: 0.6,
            transparent: true,
            opacity: 0.85
        });

        // Left eyelid (positioned above eye, hidden when eye is "open")
        STATE.leftEyelid = new THREE.Mesh(lidGeo, lidMat);
        STATE.leftEyelid.position.set(-0.1, 0.075, 0.24);
        STATE.head.add(STATE.leftEyelid);

        // Right eyelid
        STATE.rightEyelid = new THREE.Mesh(lidGeo.clone(), lidMat.clone());
        STATE.rightEyelid.position.set(0.1, 0.075, 0.24);
        STATE.head.add(STATE.rightEyelid);
    }

    // ── MOUTH BUILD (improved Shape-based) ──
    function buildMouth() {
        const mouthGeo = new THREE.SphereGeometry(0.04, 8, 6, 0, Math.PI * 2, Math.PI * 0.3, Math.PI * 0.4);
        const mouthMat = new THREE.MeshStandardMaterial({
            color: COLORS.mouthDefault,
            roughness: 0.5,
            side: THREE.DoubleSide
        });
        STATE.mouth = new THREE.Mesh(mouthGeo, mouthMat);
        STATE.mouth.position.set(0, -0.1, 0.23);
        STATE.mouth.rotation.x = Math.PI * 0.15;
        STATE.head.add(STATE.mouth);
    }

    // ── ARMS BUILD ──
    function buildArms() {
        const armGeo = new THREE.CylinderGeometry(0.06, 0.05, 0.55, 8);
        const armMat = new THREE.MeshStandardMaterial({ color: COLORS.shirt, roughness: 0.5, metalness: 0.1 });

        // Left arm
        STATE.leftArm = new THREE.Group();
        const leftArmMesh = new THREE.Mesh(armGeo, armMat);
        leftArmMesh.position.y = -0.22;
        leftArmMesh.castShadow = true;
        STATE.leftArm.add(leftArmMesh);

        // Left hand
        const handGeo = new THREE.SphereGeometry(0.055, 8, 8);
        const handMat = new THREE.MeshStandardMaterial({ color: COLORS.skin, roughness: 0.6 });
        STATE.leftHand = new THREE.Mesh(handGeo, handMat);
        STATE.leftHand.position.y = -0.5;
        STATE.leftArm.add(STATE.leftHand);
        STATE.leftArm.position.set(-0.42, 1.4, 0);
        STATE.leftArm.rotation.z = 0.15;
        STATE.avatar.add(STATE.leftArm);

        // Right arm
        STATE.rightArm = new THREE.Group();
        const rightArmMesh = new THREE.Mesh(armGeo.clone(), armMat.clone());
        rightArmMesh.position.y = -0.22;
        rightArmMesh.castShadow = true;
        STATE.rightArm.add(rightArmMesh);

        STATE.rightHand = new THREE.Mesh(handGeo.clone(), handMat.clone());
        STATE.rightHand.position.y = -0.5;
        STATE.rightArm.add(STATE.rightHand);
        STATE.rightArm.position.set(0.42, 1.4, 0);
        STATE.rightArm.rotation.z = -0.15;
        STATE.avatar.add(STATE.rightArm);
    }

    // ── LEGS BUILD ──
    function buildLegs() {
        const legGeo = new THREE.CylinderGeometry(0.09, 0.07, 0.65, 8);
        const legMat = new THREE.MeshStandardMaterial({ color: COLORS.pants, roughness: 0.7 });

        const leftLeg = new THREE.Mesh(legGeo, legMat);
        leftLeg.position.set(-0.13, 0.38, 0);
        leftLeg.castShadow = true;
        STATE.avatar.add(leftLeg);

        const rightLeg = leftLeg.clone();
        rightLeg.position.set(0.13, 0.38, 0);
        STATE.avatar.add(rightLeg);

        // Shoes
        const shoeGeo = new THREE.BoxGeometry(0.12, 0.06, 0.18);
        const shoeMat = new THREE.MeshStandardMaterial({ color: 0x222222, roughness: 0.6 });
        const leftShoe = new THREE.Mesh(shoeGeo, shoeMat);
        leftShoe.position.set(-0.13, 0.06, 0.03);
        STATE.avatar.add(leftShoe);
        const rightShoe = leftShoe.clone();
        rightShoe.position.set(0.13, 0.06, 0.03);
        STATE.avatar.add(rightShoe);
    }

    // ═══════════════════════════════════════════════
    // PLATFORM & PARTICLES
    // ═══════════════════════════════════════════════
    function createPlatform() {
        // Glowing platform disc
        const platformGeo = new THREE.CylinderGeometry(0.8, 0.9, 0.05, 24);
        const platformMat = new THREE.MeshStandardMaterial({
            color: COLORS.platform,
            roughness: 0.3,
            metalness: 0.6,
            emissive: COLORS.glowPrimary,
            emissiveIntensity: 0.08
        });
        const platform = new THREE.Mesh(platformGeo, platformMat);
        platform.position.y = 0.02;
        platform.receiveShadow = true;
        STATE.scene.add(platform);

        // Glow ring (color changes with emotion)
        const ringGeo = new THREE.TorusGeometry(0.85, 0.015, 8, 48);
        const ringMat = new THREE.MeshStandardMaterial({
            color: COLORS.glowPrimary,
            emissive: COLORS.glowPrimary,
            emissiveIntensity: 0.5,
            roughness: 0.2,
            metalness: 0.8
        });
        STATE.glowRing = new THREE.Mesh(ringGeo, ringMat);
        STATE.glowRing.position.y = 0.05;
        STATE.glowRing.rotation.x = -Math.PI / 2;
        STATE.scene.add(STATE.glowRing);
    }

    function createAmbientParticles() {
        const particleCount = 50;
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array(particleCount * 3);
        const sizes = new Float32Array(particleCount);

        for (let i = 0; i < particleCount; i++) {
            positions[i * 3] = (Math.random() - 0.5) * 8;
            positions[i * 3 + 1] = Math.random() * 5;
            positions[i * 3 + 2] = (Math.random() - 0.5) * 8;
            sizes[i] = Math.random() * 0.03 + 0.01;

            STATE.ambientParticles.push({
                speed: Math.random() * 0.003 + 0.001,
                offset: Math.random() * Math.PI * 2
            });
        }

        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

        const particleMat = new THREE.PointsMaterial({
            color: COLORS.glowPrimary,
            size: 0.04,
            transparent: true,
            opacity: 0.4,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });

        STATE.particleSystem = new THREE.Points(geometry, particleMat);
        STATE.scene.add(STATE.particleSystem);
    }

    // ═══════════════════════════════════════════════
    // ANIMATION LOOP
    // ═══════════════════════════════════════════════
    function animate() {
        requestAnimationFrame(animate);
        if (!STATE.isInitialized) return;

        const delta = STATE.clock.getDelta();
        const elapsed = STATE.clock.getElapsedTime();

        updateIdleAnimation(elapsed, delta);
        updateGesture(elapsed, delta);
        updateMouth(delta);
        updateHeadLook(delta);
        updateExpression(delta);
        updateEyebrows(delta);
        updateEyelids(elapsed, delta);
        updatePlatformGlow(delta);
        updateParticles(elapsed);

        STATE.renderer.render(STATE.scene, STATE.camera);
    }

    // ── IDLE ANIMATION ──
    function updateIdleAnimation(elapsed, delta) {
        if (!STATE.avatar) return;

        // Gentle breathing / float
        const breathe = Math.sin(elapsed * 1.5) * 0.008;
        STATE.avatar.position.y = breathe;

        // Subtle body sway
        STATE.body.rotation.z = Math.sin(elapsed * 0.7) * 0.015;

        // Eye blink (every ~4 seconds)
        const blinkCycle = elapsed % 4;
        let eyeScaleY = 1;
        if (blinkCycle > 3.8 && blinkCycle < 3.9) {
            eyeScaleY = 0.1;
        }
        if (STATE.leftEye) STATE.leftEye.scale.y = eyeScaleY;
        if (STATE.rightEye) STATE.rightEye.scale.y = eyeScaleY;

        // Subtle arm sway only during idle
        if (STATE.currentGesture === 'idle') {
            STATE.leftArm.rotation.x = Math.sin(elapsed * 0.8) * 0.05;
            STATE.rightArm.rotation.x = Math.sin(elapsed * 0.8 + 0.5) * 0.05;
        }
    }

    // ── GESTURE ANIMATION ──
    function updateGesture(elapsed, delta) {
        STATE.gestureTimer += delta;
        const t = STATE.gestureTimer;

        switch (STATE.currentGesture) {
            case 'talk':
                // Hands move expressively while speaking
                STATE.leftArm.rotation.z = 0.3 + Math.sin(elapsed * 3) * 0.2;
                STATE.leftArm.rotation.x = -0.4 + Math.sin(elapsed * 2.5) * 0.15;
                STATE.rightArm.rotation.z = -0.3 + Math.sin(elapsed * 2.8 + 1) * 0.2;
                STATE.rightArm.rotation.x = -0.3 + Math.sin(elapsed * 2.2 + 0.5) * 0.15;
                STATE.targetHeadRotY = Math.sin(elapsed * 1.5) * 0.08;
                break;

            case 'nod':
                // Nodding acknowledgment
                const nodProgress = Math.min(t / 1.5, 1);
                if (nodProgress < 1) {
                    STATE.targetHeadRotX = Math.sin(nodProgress * Math.PI * 3) * 0.15;
                } else {
                    STATE.targetHeadRotX = 0;
                    if (t > 2) {
                        STATE.currentGesture = STATE.isTalking ? 'talk' : 'idle';
                    }
                }
                break;

            case 'wave':
                // Right arm raises and waves side-to-side (greeting)
                if (t < 0.5) {
                    // Raise arm
                    const raise = t / 0.5;
                    STATE.rightArm.rotation.z = -0.15 + (-1.2 - (-0.15)) * _easeInOut(raise);
                    STATE.rightArm.rotation.x = -0.6 * _easeInOut(raise);
                } else if (t < 2.5) {
                    // Wave side to side
                    STATE.rightArm.rotation.z = -1.2 + Math.sin((t - 0.5) * 6) * 0.25;
                    STATE.rightArm.rotation.x = -0.6;
                    STATE.targetHeadRotY = Math.sin((t - 0.5) * 3) * 0.1;
                } else if (t < 3.0) {
                    // Lower arm back
                    const lower = (t - 2.5) / 0.5;
                    STATE.rightArm.rotation.z = -1.2 + (1.2 - 0.15) * _easeInOut(lower);
                    STATE.rightArm.rotation.x = -0.6 * (1 - _easeInOut(lower));
                } else {
                    STATE.currentGesture = STATE.isTalking ? 'talk' : 'idle';
                }
                // Left arm stays still
                STATE.leftArm.rotation.z += (0.15 - STATE.leftArm.rotation.z) * delta * 3;
                STATE.leftArm.rotation.x += (0 - STATE.leftArm.rotation.x) * delta * 3;
                break;

            case 'think':
                // Right hand moves to chin, head tilts slightly
                if (t < 0.6) {
                    const raise = _easeInOut(t / 0.6);
                    STATE.rightArm.rotation.z = -0.15 + (-0.8 - (-0.15)) * raise;
                    STATE.rightArm.rotation.x = -0.9 * raise;
                    STATE.targetHeadRotY = -0.12 * raise;
                    STATE.targetHeadRotX = -0.06 * raise;
                } else if (t < 2.5) {
                    // Hold thinking pose with subtle movement
                    STATE.rightArm.rotation.z = -0.8 + Math.sin(elapsed * 1.2) * 0.03;
                    STATE.rightArm.rotation.x = -0.9 + Math.sin(elapsed * 0.8) * 0.02;
                    STATE.targetHeadRotY = -0.12 + Math.sin(elapsed * 0.6) * 0.04;
                    STATE.targetHeadRotX = -0.06;
                } else if (t < 3.1) {
                    const lower = _easeInOut((t - 2.5) / 0.6);
                    STATE.rightArm.rotation.z = -0.8 + (0.8 - 0.15) * lower;
                    STATE.rightArm.rotation.x = -0.9 * (1 - lower);
                    STATE.targetHeadRotY = -0.12 * (1 - lower);
                    STATE.targetHeadRotX = -0.06 * (1 - lower);
                } else {
                    STATE.currentGesture = STATE.isTalking ? 'talk' : 'idle';
                }
                STATE.leftArm.rotation.z += (0.15 - STATE.leftArm.rotation.z) * delta * 3;
                STATE.leftArm.rotation.x += (0 - STATE.leftArm.rotation.x) * delta * 3;
                break;

            case 'celebrate':
                // Both arms raise up, body bounces
                if (t < 0.5) {
                    const raise = _easeInOut(t / 0.5);
                    STATE.leftArm.rotation.z = 0.15 + (1.3 - 0.15) * raise;
                    STATE.rightArm.rotation.z = -0.15 + (-1.3 - (-0.15)) * raise;
                    STATE.leftArm.rotation.x = -0.3 * raise;
                    STATE.rightArm.rotation.x = -0.3 * raise;
                } else if (t < 2.5) {
                    // Bounce and celebratory sway
                    STATE.avatar.position.y = Math.abs(Math.sin((t - 0.5) * 5)) * 0.04 + 0.01;
                    STATE.leftArm.rotation.z = 1.3 + Math.sin(elapsed * 4) * 0.15;
                    STATE.rightArm.rotation.z = -1.3 + Math.sin(elapsed * 4 + 0.5) * 0.15;
                    STATE.body.rotation.z = Math.sin(elapsed * 3) * 0.06;
                } else if (t < 3.0) {
                    const lower = _easeInOut((t - 2.5) / 0.5);
                    STATE.leftArm.rotation.z = 1.3 + (0.15 - 1.3) * lower;
                    STATE.rightArm.rotation.z = -1.3 + (-0.15 - (-1.3)) * lower;
                    STATE.leftArm.rotation.x = -0.3 * (1 - lower);
                    STATE.rightArm.rotation.x = -0.3 * (1 - lower);
                } else {
                    STATE.currentGesture = STATE.isTalking ? 'talk' : 'idle';
                }
                break;

            case 'point':
                // Right arm extends forward (directing attention)
                if (t < 0.4) {
                    const raise = _easeInOut(t / 0.4);
                    STATE.rightArm.rotation.z = -0.15 * (1 - raise);
                    STATE.rightArm.rotation.x = -0.7 * raise;
                    STATE.targetHeadRotX = -0.05 * raise;
                } else if (t < 2.0) {
                    STATE.rightArm.rotation.z = Math.sin(elapsed * 1.5) * 0.03;
                    STATE.rightArm.rotation.x = -0.7;
                } else if (t < 2.5) {
                    const lower = _easeInOut((t - 2.0) / 0.5);
                    STATE.rightArm.rotation.x = -0.7 * (1 - lower);
                    STATE.rightArm.rotation.z = -0.15 * lower;
                } else {
                    STATE.currentGesture = STATE.isTalking ? 'talk' : 'idle';
                }
                STATE.leftArm.rotation.z += (0.15 - STATE.leftArm.rotation.z) * delta * 3;
                STATE.leftArm.rotation.x += (0 - STATE.leftArm.rotation.x) * delta * 3;
                break;

            case 'shrug':
                // Both arms raise with palms up, head tilts
                if (t < 0.4) {
                    const raise = _easeInOut(t / 0.4);
                    STATE.leftArm.rotation.z = 0.15 + (0.8 - 0.15) * raise;
                    STATE.rightArm.rotation.z = -0.15 + (-0.8 - (-0.15)) * raise;
                    STATE.leftArm.rotation.x = -0.4 * raise;
                    STATE.rightArm.rotation.x = -0.4 * raise;
                    STATE.targetHeadRotY = 0.15 * raise;
                } else if (t < 1.5) {
                    // Hold shrug with subtle movement
                    STATE.leftArm.rotation.z = 0.8 + Math.sin(elapsed * 2) * 0.05;
                    STATE.rightArm.rotation.z = -0.8 + Math.sin(elapsed * 2 + 0.5) * 0.05;
                    STATE.targetHeadRotY = 0.15;
                } else if (t < 2.0) {
                    const lower = _easeInOut((t - 1.5) / 0.5);
                    STATE.leftArm.rotation.z = 0.8 + (0.15 - 0.8) * lower;
                    STATE.rightArm.rotation.z = -0.8 + (-0.15 - (-0.8)) * lower;
                    STATE.leftArm.rotation.x = -0.4 * (1 - lower);
                    STATE.rightArm.rotation.x = -0.4 * (1 - lower);
                    STATE.targetHeadRotY = 0.15 * (1 - lower);
                } else {
                    STATE.currentGesture = STATE.isTalking ? 'talk' : 'idle';
                }
                break;

            case 'idle':
            default:
                // Return arms to rest
                STATE.leftArm.rotation.z += (0.15 - STATE.leftArm.rotation.z) * delta * 3;
                STATE.leftArm.rotation.x += (0 - STATE.leftArm.rotation.x) * delta * 3;
                STATE.rightArm.rotation.z += (-0.15 - STATE.rightArm.rotation.z) * delta * 3;
                STATE.rightArm.rotation.x += (0 - STATE.rightArm.rotation.x) * delta * 3;
                STATE.targetHeadRotX = Math.sin(elapsed * 0.5) * 0.03;
                STATE.targetHeadRotY = Math.sin(elapsed * 0.3) * 0.05;
                break;
        }
    }

    // ── MOUTH ──
    function updateMouth(delta) {
        STATE.mouthOpenAmount += (STATE.targetMouthOpen - STATE.mouthOpenAmount) * delta * 12;

        if (STATE.mouth) {
            STATE.mouth.scale.y = 1 + STATE.mouthOpenAmount * 1.5;
            // Apply expression-driven width
            STATE.mouth.scale.x = STATE.expression.mouthWidth - STATE.mouthOpenAmount * 0.3;
            STATE.mouth.material.color.setHex(
                STATE.mouthOpenAmount > 0.3 ? COLORS.mouthOpen : COLORS.mouthDefault
            );
        }
    }

    // ── HEAD LOOK ──
    function updateHeadLook(delta) {
        STATE.headRotX += (STATE.targetHeadRotX - STATE.headRotX) * delta * 4;
        STATE.headRotY += (STATE.targetHeadRotY - STATE.headRotY) * delta * 4;

        if (STATE.head) {
            STATE.head.rotation.x = STATE.headRotX;
            STATE.head.rotation.y = STATE.headRotY;
        }
    }

    // ── EXPRESSION INTERPOLATION ──
    function updateExpression(delta) {
        const speed = delta * 3; // Smooth transition
        const e = STATE.expression;
        const t = STATE.expressionTarget;

        e.eyebrowLeftAngle += (t.eyebrowLeftAngle - e.eyebrowLeftAngle) * speed;
        e.eyebrowRightAngle += (t.eyebrowRightAngle - e.eyebrowRightAngle) * speed;
        e.eyebrowLeftY += (t.eyebrowLeftY - e.eyebrowLeftY) * speed;
        e.eyebrowRightY += (t.eyebrowRightY - e.eyebrowRightY) * speed;
        e.eyelidLeft += (t.eyelidLeft - e.eyelidLeft) * speed;
        e.eyelidRight += (t.eyelidRight - e.eyelidRight) * speed;
        e.mouthWidth += (t.mouthWidth - e.mouthWidth) * speed;
    }

    // ── EYEBROWS UPDATE ──
    function updateEyebrows(delta) {
        if (STATE.leftEyebrow) {
            STATE.leftEyebrow.rotation.z = STATE.expression.eyebrowLeftAngle;
            STATE.leftEyebrow.position.y = 0.11 + STATE.expression.eyebrowLeftY;
        }
        if (STATE.rightEyebrow) {
            STATE.rightEyebrow.rotation.z = -STATE.expression.eyebrowRightAngle; // Mirror
            STATE.rightEyebrow.position.y = 0.11 + STATE.expression.eyebrowRightY;
        }
    }

    // ── EYELIDS UPDATE ──
    function updateEyelids(elapsed, delta) {
        if (STATE.leftEyelid) {
            // Position: when eyelid = 1 (open), lid is up high (hidden above eye)
            // When eyelid = 0 (closed), lid drops down over the eye
            const openAmount = STATE.expression.eyelidLeft;
            STATE.leftEyelid.position.y = 0.045 + openAmount * 0.035;
            STATE.leftEyelid.scale.y = Math.max(0.5, 2 - openAmount * 1.5);
        }
        if (STATE.rightEyelid) {
            const openAmount = STATE.expression.eyelidRight;
            STATE.rightEyelid.position.y = 0.045 + openAmount * 0.035;
            STATE.rightEyelid.scale.y = Math.max(0.5, 2 - openAmount * 1.5);
        }
    }

    // ── PLATFORM GLOW UPDATE ──
    function updatePlatformGlow(delta) {
        if (!STATE.glowRing) return;

        const targetColor = new THREE.Color(EMOTION_GLOW[STATE.currentEmotion] || EMOTION_GLOW.neutral);

        // Smooth color transition
        STATE.glowRing.material.color.lerp(targetColor, delta * 2);
        STATE.glowRing.material.emissive.lerp(targetColor, delta * 2);

        // Update platform light color too
        if (STATE.platformLight) {
            STATE.platformLight.color.lerp(targetColor, delta * 2);
        }
    }

    // ── PARTICLES ──
    function updateParticles(elapsed) {
        if (!STATE.particleSystem) return;

        const positions = STATE.particleSystem.geometry.attributes.position.array;
        for (let i = 0; i < STATE.ambientParticles.length; i++) {
            const p = STATE.ambientParticles[i];
            positions[i * 3 + 1] += p.speed;
            positions[i * 3] += Math.sin(elapsed + p.offset) * 0.002;

            if (positions[i * 3 + 1] > 5) {
                positions[i * 3 + 1] = 0;
            }
        }
        STATE.particleSystem.geometry.attributes.position.needsUpdate = true;
    }

    // ═══════════════════════════════════════════════
    // EASING UTILITY
    // ═══════════════════════════════════════════════
    function _easeInOut(t) {
        return t < 0.5
            ? 2 * t * t
            : 1 - Math.pow(-2 * t + 2, 2) / 2;
    }

    // ═══════════════════════════════════════════════
    // PUBLIC API
    // ═══════════════════════════════════════════════

    window.AvatarController = {
        init: init,

        /**
         * Set the current gesture animation.
         * Supported: 'idle', 'talk', 'nod', 'wave', 'think', 'celebrate', 'point', 'shrug'
         */
        setGesture: function (gesture) {
            STATE.currentGesture = gesture;
            STATE.gestureTimer = 0;
        },

        /**
         * Set the current emotion expression.
         * Supported: 'happy', 'serious', 'encouraging', 'confused', 'excited', 'neutral'
         */
        setEmotion: function (emotion) {
            STATE.currentEmotion = emotion;

            // Apply the expression preset
            const preset = EXPRESSION_PRESETS[emotion] || EXPRESSION_PRESETS.neutral;
            Object.assign(STATE.expressionTarget, preset);
        },

        startTalking: function () {
            STATE.isTalking = true;
            STATE.talkStartTime = STATE.clock.getElapsedTime();
            STATE.currentGesture = 'talk';
            STATE.gestureTimer = 0;
        },

        stopTalking: function () {
            STATE.isTalking = false;
            STATE.targetMouthOpen = 0;
            STATE.currentGesture = 'idle';
        },

        setMouthOpen: function (amount) {
            STATE.targetMouthOpen = Math.max(0, Math.min(1, amount));
        },

        triggerNod: function () {
            STATE.currentGesture = 'nod';
            STATE.gestureTimer = 0;
        },

        triggerWave: function () {
            STATE.currentGesture = 'wave';
            STATE.gestureTimer = 0;
        },

        triggerThink: function () {
            STATE.currentGesture = 'think';
            STATE.gestureTimer = 0;
        },

        triggerCelebrate: function () {
            STATE.currentGesture = 'celebrate';
            STATE.gestureTimer = 0;
        },

        triggerPoint: function () {
            STATE.currentGesture = 'point';
            STATE.gestureTimer = 0;
        },

        triggerShrug: function () {
            STATE.currentGesture = 'shrug';
            STATE.gestureTimer = 0;
        },

        isReady: function () {
            return STATE.isInitialized;
        }
    };

    // ═══════════════════════════════════════════════
    // RESIZE
    // ═══════════════════════════════════════════════
    function onResize() {
        const canvas = document.getElementById('avatarCanvas');
        if (!canvas || !STATE.renderer || !STATE.camera) return;

        const w = canvas.parentElement.clientWidth;
        const h = canvas.parentElement.clientHeight;
        STATE.camera.aspect = w / h;
        STATE.camera.updateProjectionMatrix();
        STATE.renderer.setSize(w, h);
    }

    // Auto-init when DOM ready
    document.addEventListener('DOMContentLoaded', function () {
        setTimeout(init, 100);
    });

})();
