#pragma once
#include <cctype>
#include <cstddef>
#include <string>

namespace picoLichess {
// Full structural validation of a bounded JSON reply. The existing provider
// extractors run only after this passes; trailing/concatenated JSON is rejected.
class JsonDocumentValidator {
public:
    explicit JsonDocumentValidator(const std::string& input):s_(input){}
    bool valid(){size_t p=0;return value(p,0)&& (ws(p),p==s_.size());}
private:
    const std::string& s_;
    static bool digit(char c){return c>='0'&&c<='9';}
    void ws(size_t& p)const{while(p<s_.size()&&(s_[p]==' '||s_[p]=='\n'||s_[p]=='\r'||s_[p]=='\t'))++p;}
    bool literal(size_t& p,const char* l){size_t n=0;while(l[n])++n;if(s_.compare(p,n,l)!=0)return false;p+=n;return true;}
    bool str(size_t& p){
        if(p>=s_.size()||s_[p++]!='"')return false;
        while(p<s_.size()){
            unsigned char c=static_cast<unsigned char>(s_[p++]);
            if(c=='"')return true;
            if(c<0x20)return false;
            if(c!='\\')continue;
            if(p==s_.size())return false;
            char escape=s_[p++];
            if(escape=='"'||escape=='\\'||escape=='/'||escape=='b'||escape=='f'||escape=='n'||escape=='r'||escape=='t')continue;
            if(escape!='u'||s_.size()-p<4)return false;
            for(int i=0;i<4;++i){char h=s_[p++];if(!digit(h)&&!(h>='a'&&h<='f')&&!(h>='A'&&h<='F'))return false;}
        }
        return false;
    }
    bool number(size_t& p){
        if(p<s_.size()&&s_[p]=='-')++p;
        if(p==s_.size())return false;
        if(s_[p]=='0')++p;
        else if(s_[p]>='1'&&s_[p]<='9'){while(p<s_.size()&&digit(s_[p]))++p;}
        else return false;
        if(p<s_.size()&&s_[p]=='.'){++p;size_t start=p;while(p<s_.size()&&digit(s_[p]))++p;if(p==start)return false;}
        if(p<s_.size()&&(s_[p]=='e'||s_[p]=='E')){
            ++p;if(p<s_.size()&&(s_[p]=='+'||s_[p]=='-'))++p;
            size_t start=p;while(p<s_.size()&&digit(s_[p]))++p;if(p==start)return false;
        }
        return true;
    }
    bool value(size_t& p,unsigned depth){
        ws(p);if(p==s_.size()||depth>32)return false;
        char c=s_[p];
        if(c=='"')return str(p);
        if(c=='t')return literal(p,"true");
        if(c=='f')return literal(p,"false");
        if(c=='n')return literal(p,"null");
        if(c=='-'||digit(c))return number(p);
        if(c=='['){
            ++p;ws(p);if(p<s_.size()&&s_[p]==']'){++p;return true;}
            for(;;){if(!value(p,depth+1))return false;
                ws(p);
                if(p==s_.size())return false;
                if(s_[p]==']'){++p;return true;}
                if(s_[p++]!=',')return false;}
        }
        if(c=='{'){
            ++p;ws(p);if(p<s_.size()&&s_[p]=='}'){++p;return true;}
            for(;;){if(!str(p))return false;ws(p);
                if(p==s_.size()||s_[p++]!=':')return false;
                if(!value(p,depth+1))return false;
                ws(p);
                if(p==s_.size())return false;
                if(s_[p]=='}'){++p;return true;}
                if(s_[p++]!=',')return false;
                ws(p);}
        }
        return false;
    }
};
inline bool valid_json_object(const std::string& s){
    size_t p=0;while(p<s.size()&&(s[p]==' '||s[p]=='\r'||s[p]=='\n'||s[p]=='\t'))++p;
    return p<s.size()&&s[p]=='{'&&JsonDocumentValidator(s).valid();
}
}
