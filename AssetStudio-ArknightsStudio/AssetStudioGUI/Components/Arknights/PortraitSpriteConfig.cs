namespace Arknights.PortraitSpriteMono
{
    internal class PortraitRect
    {
        public float X { get; set; }
        public float Y { get; set; }
        public float W { get; set; }
        public float H { get; set; }
    }

    internal class AtlasSprite
    {
        public string Name { get; set; }
        public string Guid { get; set; }
        public int Atlas { get; set; }
        public PortraitRect Rect { get; set; }
        public bool Rotate { get; set; }
    }

    internal class TextureIDs
    {
        public int m_FileID { get; set; }
        public long m_PathID { get; set; }  
    }

    internal class AtlasInfo
    {
        public int Index { get; set; }
        public TextureIDs Texture { get; set; }
        public TextureIDs Alpha { get; set; }
        public int Size { get; set; }
    }

    internal class PortraitSpriteConfig
    {
        public string m_Name { get; set; }
        public AtlasSprite[] _sprites { get; set; }
        public AtlasInfo _atlas { get; set; }
        public int _index { get; set; }
    }
}
