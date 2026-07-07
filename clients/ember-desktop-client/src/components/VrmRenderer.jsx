import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { VRMLoaderPlugin } from '@pixiv/three-vrm';
import { Mic, MicOff, Send } from 'lucide-react';
import { AnimationManager } from '../utils/AnimationManager.js';

export default function VrmRenderer({ isThinking: isThinkingProp = false, affinity: affinityProp = 50, isCompanionMode = false, gesture, latestMessage: latestMessageProp = '' }) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const vrmRef = useRef(null);
  const mixerRef = useRef(null);
  const animManagerRef = useRef(null);
  const [loadError, setLoadError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [floatingText, setFloatingText] = useState('');

  useEffect(() => {
    if (!isCompanionMode) {
      setFloatingText(latestMessageProp);
    }
  }, [latestMessageProp, isCompanionMode]);

  const floatingTextTimeoutRef = useRef(null);
  useEffect(() => {
    if (floatingText) {
      if (floatingTextTimeoutRef.current) clearTimeout(floatingTextTimeoutRef.current);
      floatingTextTimeoutRef.current = setTimeout(() => {
        setFloatingText('');
      }, 10000);
    }
    return () => {
      if (floatingTextTimeoutRef.current) clearTimeout(floatingTextTimeoutRef.current);
    };
  }, [floatingText]);

  const isThinkingRef = useRef(isThinkingProp);
  const affinityRef = useRef(affinityProp);
  const isWalkingRef = useRef(false);
  const ipcAudioAmplitudeRef = useRef(0);
  const isMouseDownRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const gestureRef = useRef(null);

  const idleAnimTimerRef = useRef(0);
  const idleAnimDurationRef = useRef(120 + Math.random() * 180); 
  const currentIdleVariantRef = useRef('idle');
  const thinkVariantRef = useRef('think');
  const walkVariantRef = useRef('walk');

  const modelScaleRef = useRef(1.0);

  useEffect(() => {
    gestureRef.current = gesture;
  }, [gesture]);

  const [showQuickChat, setShowQuickChat] = useState(false);
  const [chatText, setChatText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [expressionOverride, setExpressionOverride] = useState(null);

  const expressionOverrideRef = useRef(null);

  useEffect(() => {
    expressionOverrideRef.current = expressionOverride;
  }, [expressionOverride]);
  const isMouseOverChatRef = useRef(false);

  const handleMicClick = () => {
    if (window.electron) {
      window.electron.ipcRenderer.send('companion-toggle-listening');
    }
  };

  const handleSendChat = () => {
    if (chatText.trim() && window.electron) {
      window.electron.ipcRenderer.send('companion-send-message', chatText);
      setChatText('');
    }
  };

  const onChatMouseEnter = () => {
    isMouseOverChatRef.current = true;
    if (window.electron) {
      window.electron.ipcRenderer.send('set-companion-click-through', false);
    }
  };

  const onChatMouseLeave = () => {
    isMouseOverChatRef.current = false;
    if (window.electron) {
      window.electron.ipcRenderer.send('set-companion-click-through', true);
    }
  };

  useEffect(() => {
    if (!isCompanionMode) {
      isThinkingRef.current = isThinkingProp;
    }
  }, [isThinkingProp, isCompanionMode]);

  const poseRef = useRef('');

  useEffect(() => {
    if (!isCompanionMode) {
      affinityRef.current = affinityProp;
    }
  }, [affinityProp, isCompanionMode]);

  useEffect(() => {
    if (isCompanionMode && window.electron) {
      const handleStateUpdate = (data) => {
        isThinkingRef.current = data.isThinking;
        affinityRef.current = data.affinity;
        if (data.pose) {
          poseRef.current = data.pose;
        }
        if (data.latestMessage && data.latestMessage !== floatingText) {
          setFloatingText(data.latestMessage);
        }
      };
      const handleAmplitudeUpdate = (amplitude) => {
        ipcAudioAmplitudeRef.current = amplitude;
      };
      const handleListeningUpdate = (event, listening) => {
        setIsListening(listening);
      };

      window.electron.ipcRenderer.on('vrm-state-update', handleStateUpdate);
      window.electron.ipcRenderer.on('vrm-audio-amplitude', handleAmplitudeUpdate);
      window.electron.ipcRenderer.on('listening-state-changed', handleListeningUpdate);

      return () => {
        window.electron.ipcRenderer.removeAllListeners('vrm-state-update');
        window.electron.ipcRenderer.removeAllListeners('vrm-audio-amplitude');
        window.electron.ipcRenderer.removeAllListeners('listening-state-changed');
      };
    }
  }, [isCompanionMode]);

  useEffect(() => {
    if (!isCompanionMode) return;

    const handleMouseDown = (e) => {
      isMouseDownRef.current = true;
      dragStartRef.current = { x: e.screenX, y: e.screenY };
    };

    const handleGlobalMouseMove = (e) => {
      if (isMouseDownRef.current && window.electron) {
        const deltaX = e.screenX - dragStartRef.current.x;
        const deltaY = e.screenY - dragStartRef.current.y;
        dragStartRef.current = { x: e.screenX, y: e.screenY };
        window.electron.ipcRenderer.send('move-companion-window', { deltaX, deltaY });
      }
    };

    const handleMouseUp = () => {
      isMouseDownRef.current = false;
    };

    window.addEventListener('mousedown', handleMouseDown);
    window.addEventListener('mousemove', handleGlobalMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      window.removeEventListener('mousedown', handleMouseDown);
      window.removeEventListener('mousemove', handleGlobalMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isCompanionMode]);

  useEffect(() => {
    if (!isCompanionMode || !window.electron) return;

    let wanderInterval;
    let moveInterval;

    const startWandering = () => {
      wanderInterval = setInterval(() => {
        if (isWalkingRef.current || isMouseDownRef.current) return;

        const targetDeltaX = (Math.random() - 0.5) * 300;
        if (Math.abs(targetDeltaX) < 40) return;

        isWalkingRef.current = true;

        if (vrmRef.current) {
          vrmRef.current.scene.rotation.y = targetDeltaX > 0 ? Math.PI / 2 : -Math.PI / 2;
        }

        let currentStep = 0;
        const totalSteps = 60;
        const stepDelta = targetDeltaX / totalSteps;

        moveInterval = setInterval(() => {
          if (isMouseDownRef.current) {
            clearInterval(moveInterval);
            isWalkingRef.current = false;
            if (vrmRef.current) vrmRef.current.scene.rotation.y = 0;
            return;
          }

          window.electron.ipcRenderer.send('move-companion-window', { deltaX: stepDelta, deltaY: 0 });
          currentStep++;

          if (currentStep >= totalSteps) {
            clearInterval(moveInterval);
            isWalkingRef.current = false;
            if (vrmRef.current) vrmRef.current.scene.rotation.y = 0;
          }
        }, 16);
      }, 15000);
    };

    startWandering();

    return () => {
      clearInterval(wanderInterval);
      clearInterval(moveInterval);
    };
  }, [isCompanionMode]);

  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const connectedAudiosRef = useRef(new WeakSet());

  useEffect(() => {
    if (!containerRef.current || !canvasRef.current) return;

    const scene = new THREE.Scene();
    scene.background = null;

    const container = containerRef.current;
    const width = container.clientWidth || 300;
    const height = container.clientHeight || 400;
    const camera = new THREE.PerspectiveCamera(isCompanionMode ? 32 : 35, width / height, 0.1, 20.0);
    if (isCompanionMode) {
      camera.position.set(0.0, 0.75, 4.8);
      camera.lookAt(new THREE.Vector3(0.0, 0.75, 0.0));
    } else {
      camera.position.set(0.0, 0.85, 3.2);
      camera.lookAt(new THREE.Vector3(0.0, 0.8, 0.0));
    }

    const renderer = new THREE.WebGLRenderer({
      canvas: canvasRef.current,
      antialias: true,
      alpha: true,
      powerPreference: "high-performance"
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = false;
    renderer.toneMapping = THREE.NoToneMapping;

    const ambientLight = new THREE.AmbientLight(0xffffff, 1.2);
    scene.add(ambientLight);
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(1.0, 2.0, 1.0);
    scene.add(dirLight);

    const loader = new GLTFLoader();
    loader.register((parser) => {
      return new VRMLoaderPlugin(parser);
    });

    loader.load(
      './Ember.vrm',
      async (gltf) => {
        const vrm = gltf.userData.vrm;
        vrmRef.current = vrm;
        scene.add(vrm.scene);

        vrm.scene.position.set(0.0, 0.0, 0.0);
        vrm.scene.rotation.y = 0.0;
        
        // Remove frustum culling to prevent glitching
        vrm.scene.traverse((obj) => {
          obj.frustumCulled = false;
        });

        if (vrm.lookAt) {
            vrm.lookAt.target = null;
        }

        animManagerRef.current = new AnimationManager(vrm);
        try {
          await animManagerRef.current.loadAnimation('idle', './animations/Sitting Idle.fbx');
          await animManagerRef.current.loadAnimation('walk', './animations/Walking.fbx');
          await animManagerRef.current.loadAnimation('think', './animations/Thinking.fbx');
          await animManagerRef.current.loadAnimation('think_stretch', './animations/Arm Stretching Think.fbx');
          await animManagerRef.current.loadAnimation('walk_turn', './animations/Catwalk Walk Turn 180 Tight.fbx');
          await animManagerRef.current.loadAnimation('angry', './animations/Angry.fbx');
          await animManagerRef.current.loadAnimation('dying', './animations/Dying.fbx');
          animManagerRef.current.playAnimation('idle', 0);
        } catch (e) {
          console.error("Failed to load animations:", e);
        }

        setLoading(false);
      },
      (progress) => {},
      (error) => {
        console.error("Error loading VRM model:", error);
        setLoadError("Failed to load 3D Model.");
        setLoading(false);
      }
    );

    let blinkTimer = 0;
    let nextBlinkTime = Math.random() * 4 + 2;
    let isBlinking = false;
    let blinkDuration = 0.15;
    let blinkElapsed = 0;

    let mouse = { x: 0, y: 0 };
    const raycaster = new THREE.Raycaster();
    const mouseVec = new THREE.Vector2();

    const handleMouseMove = (e) => {
      if (isMouseOverChatRef.current) return;
      const xNorm = (e.clientX / window.innerWidth) * 2 - 1;
      const yNorm = -(e.clientY / window.innerHeight) * 2 + 1;
      mouse.x = xNorm;
      mouse.y = yNorm;

      if (vrmRef.current) {
        mouseVec.set(xNorm, yNorm);
        raycaster.setFromCamera(mouseVec, camera);
      }
    };
    window.addEventListener('mousemove', handleMouseMove);

    const handleWheel = (e) => {
      if (isMouseOverChatRef.current) return;
      e.preventDefault();
      const scaleStep = 0.05;
      const direction = e.deltaY < 0 ? 1 : -1; 
      modelScaleRef.current = Math.max(0.5, Math.min(2.5, modelScaleRef.current + direction * scaleStep));
      
      if (isCompanionMode && window.electron) {
        window.electron.ipcRenderer.send('resize-companion-window', modelScaleRef.current);
      } else if (vrmRef.current) {
        const s = modelScaleRef.current;
        vrmRef.current.scene.scale.set(s, s, s);
      }
    };
    window.addEventListener('wheel', handleWheel, { passive: false });

    const handleCanvasClick = (e) => {
      if (!isCompanionMode) return;
      if (isMouseOverChatRef.current) return;
      
      const dx = Math.abs(e.screenX - dragStartRef.current.x);
      const dy = Math.abs(e.screenY - dragStartRef.current.y);
      if (dx > 5 || dy > 5) return; 

      if (vrmRef.current) {
        const rect = canvasRef.current.getBoundingClientRect();
        const clickX = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        const clickY = -((e.clientY - rect.top) / rect.height) * 2 + 1;
        
        mouseVec.set(clickX, clickY);
        raycaster.setFromCamera(mouseVec, camera);
        const intersects = raycaster.intersectObject(vrmRef.current.scene, true);
        
        if (intersects.length > 0) {
          const hitMesh = intersects[0].object;
          let hitHead = false;
          let parent = hitMesh;
          while(parent) {
              if (parent.name.toLowerCase().includes('head') || parent.name.toLowerCase().includes('hair') || parent.name.toLowerCase().includes('face')) {
                  hitHead = true;
                  break;
              }
              parent = parent.parent;
          }

          if (hitHead) setExpressionOverride({ type: 'headpat', time: Date.now() });
          else setExpressionOverride({ type: 'poke', time: Date.now() });

          setShowQuickChat(prev => !prev);
        }
      }
    };
    window.addEventListener('click', handleCanvasClick);

    let saccadeTimer = 0;
    let lookAwayTimer = 0;
    let isLookingAway = false;
    let currentSaccadeOffset = { x: 0, y: 0 };
    let currentLookAwayOffset = { x: 0, y: 0 };
    const lambda = 4.0; 

    let lastTime = performance.now();
    let elapsedTime = 0;

    let animationFrameId;
    let delta = 0;
    
    // Create a target position for lookAt
    const lookAtTarget = new THREE.Object3D();
    scene.add(lookAtTarget);

    let isVisible = true;
    const handleVisibilityChange = (event, state) => {
      const nextVisible = state === 'visible';
      if (nextVisible !== isVisible) {
        isVisible = nextVisible;
        if (isVisible) {
          lastTime = performance.now();
          cancelAnimationFrame(animationFrameId);
          animate();
        }
      }
    };

    const handleDocVisibilityChange = () => {
      const nextVisible = document.visibilityState === 'visible';
      if (nextVisible !== isVisible) {
        isVisible = nextVisible;
        if (isVisible) {
          lastTime = performance.now();
          cancelAnimationFrame(animationFrameId);
          animate();
        }
      }
    };

    if (window.electron) {
      window.electron.ipcRenderer.on('window-visibility-change', handleVisibilityChange);
    }
    document.addEventListener('visibilitychange', handleDocVisibilityChange);

    const animate = () => {
      if (!isVisible) return;
      animationFrameId = requestAnimationFrame(animate);
      
      const now = performance.now();
      const isIdle = !isThinkingRef.current && !isWalkingRef.current && (ipcAudioAmplitudeRef.current || 0) < 5 && (!expressionOverrideRef.current || (now - expressionOverrideRef.current.time > 3000));
      if (isIdle && now - lastTime < 33) return; // Throttle to ~30 FPS when idle

      delta = (now - lastTime) / 1000;
      lastTime = now;
      elapsedTime += delta;

      if (vrmRef.current) {
        const vrm = vrmRef.current;
        const isThinkingVal = isThinkingRef.current;
        const affinityVal = affinityRef.current;

        let targetAngry = 0.0;
        let targetSad = 0.0;
        let targetSurprised = 0.0;
        let targetHappy = 0.0;
        let targetBlinkOverride = null;

        const poseVal = poseRef.current;

        if (poseVal === 'pout' || (affinityVal < 20 && !isThinkingVal)) {
          targetAngry = 0.3; targetSad = 0.4; targetSurprised = 0.2; 
        } else if (isThinkingVal) {
          targetAngry = 0.25; targetSad = 0.15;
        } else if (affinityVal < 35) {
          targetAngry = 0.15; targetSad = 0.1;
        }

        const isWalkingVal = isWalkingRef.current;
        const expr = expressionOverrideRef.current;
        if (expr && Date.now() - expr.time < 3000) {
            if (expr.type === 'poke') targetSurprised = 0.8;
            else if (expr.type === 'headpat') { targetHappy = 1.0; targetBlinkOverride = 1.0; }
        }
        
        if (animManagerRef.current) {
            animManagerRef.current.update(delta);

            if (isWalkingVal) {
                animManagerRef.current.playAnimation(walkVariantRef.current, 0.5, 1.0);
            } else if (affinityVal < 20 && !isThinkingVal) {
                animManagerRef.current.playAnimation('angry', 0.5, 1.0);
            } else if (isThinkingVal) {
                animManagerRef.current.playAnimation(thinkVariantRef.current, 0.5, 0.7);
            } else {
                idleAnimTimerRef.current += delta;
                if (idleAnimTimerRef.current >= idleAnimDurationRef.current) {
                    idleAnimTimerRef.current = 0;
                    idleAnimDurationRef.current = 120 + Math.random() * 180;
                    currentIdleVariantRef.current = 'idle';
                    
                    thinkVariantRef.current = Math.random() < 0.5 ? 'think' : 'think_stretch';
                    walkVariantRef.current = Math.random() < 0.6 ? 'walk' : 'walk_turn';
                }
                animManagerRef.current.playAnimation(currentIdleVariantRef.current, 0.5, 0.4);
            }
        }

        if (vrm.lookAt) {
            saccadeTimer -= delta;
            lookAwayTimer -= delta;
            if (lookAwayTimer <= 0) {
              isLookingAway = !isLookingAway;
              if (isLookingAway) {
                lookAwayTimer = 5.0 + Math.random() * 10.0;
                currentLookAwayOffset = { x: (Math.random() - 0.5) * 2.0, y: (Math.random() - 0.5) * 1.0 };
              }
            }
            if (saccadeTimer <= 0 && !isLookingAway) {
              saccadeTimer = 2.0 + Math.random() * 4.0; 
              currentSaccadeOffset.x = (Math.random() - 0.5) * 0.2;
              currentSaccadeOffset.y = (Math.random() - 0.5) * 0.2;
            } else if (isLookingAway) {
              currentSaccadeOffset = { x: 0, y: 0 };
            }

            let targetLookX = (mouse.x * 2.0) + currentSaccadeOffset.x + currentLookAwayOffset.x;
            let targetLookY = (mouse.y * 1.5) + currentSaccadeOffset.y + currentLookAwayOffset.y; 

            if (expr && expr.type === 'poke' && Date.now() - expr.time < 3000) {
              targetLookX = mouse.x * 2.0;
              targetLookY = mouse.y * 1.5;
            }
            
            lookAtTarget.position.x = THREE.MathUtils.damp(lookAtTarget.position.x, targetLookX, lambda * 1.5, delta);
            lookAtTarget.position.y = THREE.MathUtils.damp(lookAtTarget.position.y, targetLookY + 1.4, lambda * 1.5, delta);
            lookAtTarget.position.z = THREE.MathUtils.damp(lookAtTarget.position.z, camera.position.z - 1.0, lambda * 1.5, delta);
            
            vrm.lookAt.lookAt(lookAtTarget.position);
        }

        let targetBlink = 0;
        if (targetBlinkOverride !== null) {
            targetBlink = targetBlinkOverride;
        } else {
            blinkTimer += delta;
            if (!isBlinking && blinkTimer >= nextBlinkTime) {
              isBlinking = true;
              blinkElapsed = 0;
            }
            if (isBlinking) {
              blinkElapsed += delta;
              if (blinkElapsed < blinkDuration / 2) targetBlink = blinkElapsed / (blinkDuration / 2);
              else if (blinkElapsed < blinkDuration) targetBlink = 1 - ((blinkElapsed - blinkDuration / 2) / (blinkDuration / 2));
              else {
                isBlinking = false;
                blinkTimer = 0;
                nextBlinkTime = Math.random() * 5 + 3; 
              }
            }
        }

        let average = 0;
        if (isCompanionMode) average = ipcAudioAmplitudeRef.current;
        else if (analyserRef.current) {
            const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
            analyserRef.current.getByteFrequencyData(dataArray);
            let sum = 0;
            for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
            average = sum / dataArray.length; 
        }

        const mouthOpen = Math.min(average / 60, 1.0);
        
        if (vrm.expressionManager) {
            vrm.expressionManager.setValue('blink', targetBlink);
            vrm.expressionManager.setValue('aa', mouthOpen);
            vrm.expressionManager.setValue('angry', targetAngry);
            vrm.expressionManager.setValue('sad', targetSad);
            vrm.expressionManager.setValue('surprised', targetSurprised);
            vrm.expressionManager.setValue('happy', targetHappy);
        }
        
        vrm.update(delta);
      }

      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      if (!containerRef.current) return;
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('wheel', handleWheel);
      window.removeEventListener('click', handleCanvasClick);
      if (window.electron) {
        window.electron.ipcRenderer.removeAllListeners('window-visibility-change');
      }
      document.removeEventListener('visibilitychange', handleDocVisibilityChange);
      renderer.dispose();
    };
  }, []);

  useEffect(() => {
    if (isCompanionMode) return;
    const handleAudioStart = (e) => {
      const audio = e.detail?.audio;
      if (!audio) return;
      if (connectedAudiosRef.current.has(audio)) return;
      connectedAudiosRef.current.add(audio);
      try {
        if (!audioContextRef.current) {
          const AudioContextClass = window.AudioContext || window.webkitAudioContext;
          audioContextRef.current = new AudioContextClass();
          analyserRef.current = audioContextRef.current.createAnalyser();
          analyserRef.current.fftSize = 256;
        }
        if (audioContextRef.current.state === 'suspended') audioContextRef.current.resume();
        const source = audioContextRef.current.createMediaElementSource(audio);
        source.connect(analyserRef.current);
        analyserRef.current.connect(audioContextRef.current.destination);
      } catch (err) {
        console.warn("Failed to connect Web Audio analyzer", err);
      }
    };
    window.addEventListener('ember-audio-start', handleAudioStart);
    return () => window.removeEventListener('ember-audio-start', handleAudioStart);
  }, []);

  return (
    <div 
      ref={containerRef} 
      className="vrm-container"
      style={{ 
        width: '100%', 
        height: '100%', 
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden'
      }}
    >
      {loading && (
        <div style={{ position: 'absolute', color: '#e63946', fontSize: '14px', zIndex: 10 }}>
          Summoning Ember...
        </div>
      )}
      {loadError && (
        <div style={{ position: 'absolute', color: '#721c24', fontSize: '12px', zIndex: 10, textAlign: 'center', padding: '10px' }}>
          {loadError}
          <br/>
          <span style={{ fontSize: '10px', color: '#888' }}>Showing 2D presence instead.</span>
        </div>
      )}
      <canvas 
        ref={canvasRef} 
        style={{ 
          width: '100%', 
          height: '100%', 
          outline: 'none',
          display: loadError ? 'none' : 'block' 
        }} 
      />
      {isCompanionMode && (
        <div 
          style={{
            position: 'absolute',
            top: '15%',
            bottom: '5%',
            left: '15%',
            right: '15%',
            zIndex: 40,
            cursor: 'grab'
          }}
          onMouseEnter={() => {
            if (window.electron && !isMouseOverChatRef.current) {
              window.electron.ipcRenderer.send('set-companion-click-through', false);
            }
          }}
          onMouseLeave={() => {
            if (window.electron && !isMouseOverChatRef.current) {
              window.electron.ipcRenderer.send('set-companion-click-through', true);
            }
          }}
          onClick={(e) => {
            if (isMouseOverChatRef.current) return;
            const dx = Math.abs(e.screenX - dragStartRef.current.x);
            const dy = Math.abs(e.screenY - dragStartRef.current.y);
            if (dx > 5 || dy > 5) return; // Ignore drags
            
            setExpressionOverride({ type: 'poke', time: Date.now() });
            setShowQuickChat(prev => !prev);
          }}
        />
      )}
      {floatingText && (
        <div style={{
          position: 'absolute',
          top: '20px',
          left: '50%',
          transform: 'translateX(-50%)',
          color: '#fff',
          fontSize: '14px',
          fontWeight: '500',
          textShadow: '0px 1px 3px rgba(0,0,0,0.8)',
          pointerEvents: 'none',
          zIndex: 50,
          textAlign: 'center',
          maxWidth: '80%',
          opacity: 0.9
        }}>
          {floatingText}
        </div>
      )}
      {showQuickChat && (
        <div 
          style={{
            position: 'absolute',
            bottom: '15px',
            left: '15px',
            right: '15px',
            background: 'rgba(20, 20, 20, 0.75)',
            backdropFilter: 'blur(10px)',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            borderRadius: '12px',
            padding: '10px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            zIndex: 100,
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)'
          }}
          onMouseEnter={onChatMouseEnter}
          onMouseLeave={onChatMouseLeave}
        >
          <button
            onClick={handleMicClick}
            style={{
              background: isListening ? '#e63946' : 'rgba(255, 255, 255, 0.1)',
              border: 'none',
              borderRadius: '50%',
              width: '32px',
              height: '32px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              color: '#fff',
              transition: 'all 0.2s',
              outline: 'none'
            }}
            title={isListening ? "Stop listening" : "Start listening"}
          >
            {isListening ? (
              <Mic size={16} />
            ) : (
              <MicOff size={16} />
            )}
          </button>
          <input
            type="text"
            value={chatText}
            onChange={(e) => setChatText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSendChat();
            }}
            placeholder="Talk to Ember..."
            style={{
              flex: 1,
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '8px',
              padding: '6px 10px',
              color: '#fff',
              fontSize: '13px',
              outline: 'none'
            }}
          />
          <button
            onClick={handleSendChat}
            style={{
              background: 'rgba(255, 255, 255, 0.1)',
              border: 'none',
              borderRadius: '8px',
              width: '30px',
              height: '30px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              color: '#fff',
              outline: 'none'
            }}
          >
            <Send size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
