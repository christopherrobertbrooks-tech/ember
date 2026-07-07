import * as THREE from 'three';
import { FBXLoader } from 'three/examples/jsm/loaders/FBXLoader.js';
import { retargetAnimation } from 'vrm-mixamo-retarget';

export class AnimationManager {
    constructor(vrm) {
        this.vrm = vrm;
        this.mixer = new THREE.AnimationMixer(vrm.scene);
        this.actions = {};
        this.currentAction = null;
        this.currentActionName = null;
        this.fbxLoader = new FBXLoader();
    }

    async loadAnimation(name, url) {
        return new Promise((resolve, reject) => {
            this.fbxLoader.load(url, (fbxAsset) => {
                if (!fbxAsset.animations || fbxAsset.animations.length === 0) {
                    reject(new Error(`No animation found in ${url}`));
                    return;
                }

                const retargetedClip = retargetAnimation(fbxAsset, this.vrm);
                if (!retargetedClip) {
                    reject(new Error(`Failed to retarget animation ${name}`));
                    return;
                }
                retargetedClip.name = name;

                const action = this.mixer.clipAction(retargetedClip);
                
                action.clampWhenFinished = false;
                action.loop = THREE.LoopRepeat;
                action.setEffectiveWeight(1.0);
                
                this.actions[name] = action;
                resolve(action);
            }, undefined, reject);
        });
    }

    playAnimation(name, fadeDuration = 0.5, timeScale = 1.0) {
        const nextAction = this.actions[name];
        if (!nextAction) return;

        if (this.currentActionName === name) {
            nextAction.setEffectiveTimeScale(timeScale);
            return;
        }

        nextAction.reset();
        nextAction.setEffectiveTimeScale(timeScale);
        nextAction.play();

        if (this.currentAction) {
            this.currentAction.crossFadeTo(nextAction, fadeDuration, true);
        }

        this.currentAction = nextAction;
        this.currentActionName = name;
    }

    update(delta) {
        if (this.mixer) {
            this.mixer.update(delta);
        }
    }
}
