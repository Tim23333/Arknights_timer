using AssetStudio;

namespace CubismLive2DExtractor
{
    public class CubismPhysicsNormalizationTuplet
    {
        public float Maximum;
        public float Minimum;
        public float Default;
    }

    public class CubismPhysicsNormalization
    {
        public CubismPhysicsNormalizationTuplet Position;
        public CubismPhysicsNormalizationTuplet Angle;
    }

    public class CubismPhysicsParticle
    {
        public Vector2 InitialPosition;
        public float Mobility;
        public float Delay;
        public float Acceleration;
        public float Radius;
    }

    public class CubismPhysicsOutput
    {
        public string DestinationId;
        public int ParticleIndex;
        public Vector2 TranslationScale;
        public float AngleScale;
        public float Weight;
        public CubismPhysicsSourceComponent SourceComponent;
        public bool IsInverted;
    }

    public enum CubismPhysicsSourceComponent
    {
        X,
        Y,
        Angle,
    }

    public class CubismPhysicsInput
    {
        public string SourceId;
        public Vector2 ScaleOfTranslation;
        public float AngleScale;
        public float Weight;
        public CubismPhysicsSourceComponent SourceComponent;
        public bool IsInverted;
    }

    public class CubismPhysicsSubRig
    {
        public CubismPhysicsInput[] Input;
        public CubismPhysicsOutput[] Output;
        public CubismPhysicsParticle[] Particles;
        public CubismPhysicsNormalization Normalization;
    }

    public class CubismPhysicsRig
    {
        public CubismPhysicsSubRig[] SubRigs;
        public Vector2 Gravity = new Vector2(0, -1);
        public Vector2 Wind;
    }

    public class CubismPhysics
    {
        public string m_Name;
        public CubismPhysicsRig _rig;
    }
}
