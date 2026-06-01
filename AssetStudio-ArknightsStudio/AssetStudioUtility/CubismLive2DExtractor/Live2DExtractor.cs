////
// Based on UnityLive2DExtractorMod by aelurum
// https://github.com/aelurum/UnityLive2DExtractor
//
// Original version - by Perfare
// https://github.com/Perfare/UnityLive2DExtractor
////

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using AssetStudio;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace CubismLive2DExtractor
{
    public static class Live2DExtractor
    {
        public static void ExtractLive2D(IGrouping<string, AssetStudio.Object> assets, string destPath, string modelName, AssemblyLoader assemblyLoader, Live2DMotionMode motionMode, bool forceBezier = false)
        {            
            var destTexturePath = Path.Combine(destPath, "textures") + Path.DirectorySeparatorChar;
            var destMotionPath = Path.Combine(destPath, "motions") + Path.DirectorySeparatorChar;
            var destExpressionPath = Path.Combine(destPath, "expressions") + Path.DirectorySeparatorChar;
            Directory.CreateDirectory(destPath);
            Directory.CreateDirectory(destTexturePath);

            var expressionList = new List<MonoBehaviour>();
            var fadeMotionList = new List<MonoBehaviour>();
            var gameObjects = new List<GameObject>();
            var animationClips = new List<AnimationClip>();

            var textures = new SortedSet<string>();
            var eyeBlinkParameters = new HashSet<string>();
            var lipSyncParameters = new HashSet<string>();
            var parameterNames = new HashSet<string>();
            var partNames = new HashSet<string>();
            MonoBehaviour physics = null;

            foreach (var asset in assets)
            {
                switch (asset)
                {
                    case MonoBehaviour m_MonoBehaviour:
                        if (m_MonoBehaviour.m_Script.TryGet(out var m_Script))
                        {
                            switch (m_Script.m_ClassName)
                            {
                                case "CubismMoc":
                                    File.WriteAllBytes($"{destPath}{modelName}.moc3", ParseMoc(m_MonoBehaviour)); //moc
                                    break;
                                case "CubismPhysicsController":
                                    physics = physics ?? m_MonoBehaviour;
                                    break;
                                case "CubismExpressionData":
                                    expressionList.Add(m_MonoBehaviour);
                                    break;
                                case "CubismFadeMotionData":
                                    fadeMotionList.Add(m_MonoBehaviour);
                                    break;
                                case "CubismEyeBlinkParameter":
                                    if (m_MonoBehaviour.m_GameObject.TryGet(out var blinkGameObject))
                                    {
                                        eyeBlinkParameters.Add(blinkGameObject.m_Name);
                                    }
                                    break;
                                case "CubismMouthParameter":
                                    if (m_MonoBehaviour.m_GameObject.TryGet(out var mouthGameObject))
                                    {
                                        lipSyncParameters.Add(mouthGameObject.m_Name);
                                    }
                                    break;
                                case "CubismParameter":
                                    if (m_MonoBehaviour.m_GameObject.TryGet(out var paramGameObject))
                                    {
                                        parameterNames.Add(paramGameObject.m_Name);
                                    }
                                    break;
                                case "CubismPart":
                                    if (m_MonoBehaviour.m_GameObject.TryGet(out var partGameObject))
                                    {
                                        partNames.Add(partGameObject.m_Name);
                                    }
                                    break;
                            }
                        }
                        break;
                    case Texture2D m_Texture2D:
                        using (var image = m_Texture2D.ConvertToImage(flip: true))
                        {
                            using (var file = File.OpenWrite($"{destTexturePath}{m_Texture2D.m_Name}.png"))
                            {
                                image.WriteToStream(file, ImageFormat.Png);
                            }
                            textures.Add($"textures/{m_Texture2D.m_Name}.png"); //texture
                        }
                        break;
                    case GameObject m_GameObject:
                        gameObjects.Add(m_GameObject);
                        break;
                    case AnimationClip m_AnimationClip:
                        animationClips.Add(m_AnimationClip);
                        break;
                }
            }

            if (textures.Count == 0)
            {
                Logger.Warning($"No textures found for \"{modelName}\" model.");
            }

            //physics
            if (physics != null)
            {
                try
                {
                    var buff = ParsePhysics(physics, assemblyLoader);
                    File.WriteAllText($"{destPath}{modelName}.physics3.json", buff);
                }
                catch (Exception e)
                {
                    Logger.Warning($"Error in parsing physics data: {e.Message}");
                    physics = null;
                }
            }

            //motion
            var motions = new SortedDictionary<string, JArray>();

            if (motionMode == Live2DMotionMode.MonoBehaviour && fadeMotionList.Count > 0)  //motion from MonoBehaviour
            {
                Logger.Debug("Motion export method: MonoBehaviour (Fade motion)");
                Directory.CreateDirectory(destMotionPath);
                foreach (var fadeMotionMono in fadeMotionList)
                {
                    var fadeMotionObj = fadeMotionMono.ToType();
                    if (fadeMotionObj == null)
                    {
                        var m_Type = fadeMotionMono.ConvertToTypeTree(assemblyLoader);
                        fadeMotionObj = fadeMotionMono.ToType(m_Type);
                        if (fadeMotionObj == null)
                        {
                            Logger.Warning($"Fade motion \"{fadeMotionMono.m_Name}\" is not readable.");
                            continue;
                        }
                    }
                    var fadeMotion = JsonConvert.DeserializeObject<CubismFadeMotion>(JsonConvert.SerializeObject(fadeMotionObj));
                    if (fadeMotion.ParameterIds.Length == 0)
                        continue;

                    var motionJson = new CubismMotion3Json(fadeMotion, parameterNames, partNames, forceBezier);

                    var animName = Path.GetFileNameWithoutExtension(fadeMotion.m_Name);
                    if (motions.ContainsKey(animName))
                    {
                        animName = $"{animName}_{fadeMotion.GetHashCode()}";

                        if (motions.ContainsKey(animName))
                            continue;
                    }
                    var motionPath = new JObject(new JProperty("File", $"motions/{animName}.motion3.json"));
                    motions.Add(animName, new JArray(motionPath));
                    File.WriteAllText($"{destMotionPath}{animName}.motion3.json", JsonConvert.SerializeObject(motionJson, Formatting.Indented, new MyJsonConverter()));
                }
            }
            else if (gameObjects.Count > 0)  //motion from AnimationClip
            {
                var exportMethod = motionMode == Live2DMotionMode.AnimationClip
                    ? "AnimationClip"
                    : "AnimationClip (no Fade motions found)";
                Logger.Debug($"Motion export method: {exportMethod}");
                var rootTransform = gameObjects[0].m_Transform;
                while (rootTransform.m_Father.TryGet(out var m_Father))
                {
                    rootTransform = m_Father;
                }
                rootTransform.m_GameObject.TryGet(out var rootGameObject);
                var converter = new CubismMotion3Converter(rootGameObject, animationClips.ToArray());
                if (converter.AnimationList.Count > 0)
                {
                    Directory.CreateDirectory(destMotionPath);
                }
                foreach (var animation in converter.AnimationList)
                {
                    var motionJson = new CubismMotion3Json(animation, forceBezier);

                    var animName = animation.Name;
                    if (motions.ContainsKey(animName))
                    {
                        animName = $"{animName}_{animation.GetHashCode()}";
                        
                        if (motions.ContainsKey(animName))
                            continue;
                    }
                    var motionPath = new JObject(new JProperty("File", $"motions/{animName}.motion3.json"));
                    motions.Add(animName, new JArray(motionPath));
                    File.WriteAllText($"{destMotionPath}{animName}.motion3.json", JsonConvert.SerializeObject(motionJson, Formatting.Indented, new MyJsonConverter()));
                }
            }
            if (motions.Count == 0)
            {
                Logger.Warning($"No motions found for \"{modelName}\" model.");
            }

            //expression
            var expressions = new JArray();
            if (expressionList.Count > 0)
            {
                Directory.CreateDirectory(destExpressionPath);
            }
            foreach (var monoBehaviour in expressionList)
            {
                var expressionName = monoBehaviour.m_Name.Replace(".exp3", "");
                var expressionObj = monoBehaviour.ToType();
                if (expressionObj == null)
                {
                    var m_Type = monoBehaviour.ConvertToTypeTree(assemblyLoader);
                    expressionObj = monoBehaviour.ToType(m_Type);
                    if (expressionObj == null)
                    {
                        Logger.Warning($"Expression \"{expressionName}\" is not readable.");
                        continue;
                    }
                }
                var expression = JsonConvert.DeserializeObject<CubismExpression3Json>(JsonConvert.SerializeObject(expressionObj));

                expressions.Add(new JObject
                    {
                        { "Name", expressionName },
                        { "File", $"expressions/{expressionName}.exp3.json" }
                    });
                File.WriteAllText($"{destExpressionPath}{expressionName}.exp3.json", JsonConvert.SerializeObject(expression, Formatting.Indented));
            }

            //group
            var groups = new List<CubismModel3Json.SerializableGroup>();

            //Try looking for group IDs among the gameObjects
            if (eyeBlinkParameters.Count == 0)
            {
                eyeBlinkParameters = gameObjects.Where(x =>
                    x.m_Name.ToLower().Contains("eye")
                    && x.m_Name.ToLower().Contains("open")
                    && (x.m_Name.ToLower().Contains('l') || x.m_Name.ToLower().Contains('r'))
                ).Select(x => x.m_Name).ToHashSet();
            }
            if (lipSyncParameters.Count == 0)
            {
                lipSyncParameters = gameObjects.Where(x =>
                    x.m_Name.ToLower().Contains("mouth")
                    && x.m_Name.ToLower().Contains("open")
                    && x.m_Name.ToLower().Contains('y')
                ).Select(x => x.m_Name).ToHashSet();
            }

            groups.Add(new CubismModel3Json.SerializableGroup
            {
                Target = "Parameter",
                Name = "EyeBlink",
                Ids = eyeBlinkParameters.ToArray()
            });
            groups.Add(new CubismModel3Json.SerializableGroup
            {
                Target = "Parameter",
                Name = "LipSync",
                Ids = lipSyncParameters.ToArray()
            });

            //model
            var model3 = new CubismModel3Json
            {
                Version = 3,
                Name = modelName,
                FileReferences = new CubismModel3Json.SerializableFileReferences
                {
                    Moc = $"{modelName}.moc3",
                    Textures = textures.ToArray(),
                    Motions = JObject.FromObject(motions),
                    Expressions = expressions,
                },
                Groups = groups.ToArray()
            };
            if (physics != null)
            {
                model3.FileReferences.Physics = $"{modelName}.physics3.json";
            }
            File.WriteAllText($"{destPath}{modelName}.model3.json", JsonConvert.SerializeObject(model3, Formatting.Indented));
        }

        private static string ParsePhysics(MonoBehaviour physics, AssemblyLoader assemblyLoader)
        {
            var physicsObj = physics.ToType();
            if (physicsObj == null)
            {
                var m_Type = physics.ConvertToTypeTree(assemblyLoader);
                physicsObj = physics.ToType(m_Type);
                if (physicsObj == null)
                {
                    throw new Exception("MonoBehaviour is not readable.");
                }
            }
            var cubismPhysicsRig = JsonConvert.DeserializeObject<CubismPhysics>(JsonConvert.SerializeObject(physicsObj))._rig;

            var physicsSettings = new CubismPhysics3Json.SerializablePhysicsSettings[cubismPhysicsRig.SubRigs.Length];
            for (int i = 0; i < physicsSettings.Length; i++)
            {
                var subRigs = cubismPhysicsRig.SubRigs[i];
                physicsSettings[i] = new CubismPhysics3Json.SerializablePhysicsSettings
                {
                    Id = $"PhysicsSetting{i + 1}",
                    Input = new CubismPhysics3Json.SerializableInput[subRigs.Input.Length],
                    Output = new CubismPhysics3Json.SerializableOutput[subRigs.Output.Length],
                    Vertices = new CubismPhysics3Json.SerializableVertex[subRigs.Particles.Length],
                    Normalization = new CubismPhysics3Json.SerializableNormalization
                    {
                        Position = new CubismPhysics3Json.SerializableNormalizationValue
                        {
                            Minimum = subRigs.Normalization.Position.Minimum,
                            Default = subRigs.Normalization.Position.Default,
                            Maximum = subRigs.Normalization.Position.Maximum
                        },
                        Angle = new CubismPhysics3Json.SerializableNormalizationValue
                        {
                            Minimum = subRigs.Normalization.Angle.Minimum,
                            Default = subRigs.Normalization.Angle.Default,
                            Maximum = subRigs.Normalization.Angle.Maximum
                        }
                    }
                };
                for (int j = 0; j < subRigs.Input.Length; j++)
                {
                    var input = subRigs.Input[j];
                    physicsSettings[i].Input[j] = new CubismPhysics3Json.SerializableInput
                    {
                        Source = new CubismPhysics3Json.SerializableParameter
                        {
                            Target = "Parameter", //同名GameObject父节点的名称
                            Id = input.SourceId
                        },
                        Weight = input.Weight,
                        Type = Enum.GetName(typeof(CubismPhysicsSourceComponent), input.SourceComponent),
                        Reflect = input.IsInverted
                    };
                }
                for (int j = 0; j < subRigs.Output.Length; j++)
                {
                    var output = subRigs.Output[j];
                    physicsSettings[i].Output[j] = new CubismPhysics3Json.SerializableOutput
                    {
                        Destination = new CubismPhysics3Json.SerializableParameter
                        {
                            Target = "Parameter", //同名GameObject父节点的名称
                            Id = output.DestinationId
                        },
                        VertexIndex = output.ParticleIndex,
                        Scale = output.AngleScale,
                        Weight = output.Weight,
                        Type = Enum.GetName(typeof(CubismPhysicsSourceComponent), output.SourceComponent),
                        Reflect = output.IsInverted
                    };
                }
                for (int j = 0; j < subRigs.Particles.Length; j++)
                {
                    var particles = subRigs.Particles[j];
                    physicsSettings[i].Vertices[j] = new CubismPhysics3Json.SerializableVertex
                    {
                        Position = particles.InitialPosition,
                        Mobility = particles.Mobility,
                        Delay = particles.Delay,
                        Acceleration = particles.Acceleration,
                        Radius = particles.Radius
                    };
                }
            }
            var physicsDictionary = new CubismPhysics3Json.SerializablePhysicsDictionary[physicsSettings.Length];
            for (int i = 0; i < physicsSettings.Length; i++)
            {
                physicsDictionary[i] = new CubismPhysics3Json.SerializablePhysicsDictionary
                {
                    Id = $"PhysicsSetting{i + 1}",
                    Name = $"Dummy{i + 1}"
                };
            }
            var physicsJson = new CubismPhysics3Json
            {
                Version = 3,
                Meta = new CubismPhysics3Json.SerializableMeta
                {
                    PhysicsSettingCount = cubismPhysicsRig.SubRigs.Length,
                    TotalInputCount = cubismPhysicsRig.SubRigs.Sum(x => x.Input.Length),
                    TotalOutputCount = cubismPhysicsRig.SubRigs.Sum(x => x.Output.Length),
                    VertexCount = cubismPhysicsRig.SubRigs.Sum(x => x.Particles.Length),
                    EffectiveForces = new CubismPhysics3Json.SerializableEffectiveForces
                    {
                        Gravity = cubismPhysicsRig.Gravity,
                        Wind = cubismPhysicsRig.Wind
                    },
                    PhysicsDictionary = physicsDictionary
                },
                PhysicsSettings = physicsSettings
            };
            return JsonConvert.SerializeObject(physicsJson, Formatting.Indented, new MyJsonConverter2());
        }

        private static byte[] ParseMoc(MonoBehaviour moc)
        {
            var reader = moc.reader;
            reader.Reset();
            reader.Position += 28; //PPtr<GameObject> m_GameObject, m_Enabled, PPtr<MonoScript>
            reader.ReadAlignedString(); //m_Name
            return reader.ReadBytes(reader.ReadInt32());
        }
    }
}
