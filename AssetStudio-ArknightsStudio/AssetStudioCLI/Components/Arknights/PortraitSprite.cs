using AssetStudio;


namespace Arknights
{
    internal class PortraitSprite
    {
        public string Name { get; set; }
        public ClassIDType Type { get; }
        public SerializedFile AssetsFile { get; set; }
        public string Container { get; set; }
        public Texture2D Texture { get; set; }
        public Texture2D AlphaTexture { get; set; }
        public Rectf TextureRect { get; set; }
        public bool Rotate { get; set; }
        public float DownscaleMultiplier { get; }

        public PortraitSprite()
        {
            Type = ClassIDType.AkPortraitSprite;
            DownscaleMultiplier = 1f;
        }
    }
}
