drop database if exists viagem_app;
create database viagem_app;
use viagem_app; 

drop table if exists paises;
create table paises (
	id_pais int primary key auto_increment,
    pais varchar(50) not null,
    moeda varchar(20) not null,
    cod_moeda varchar(10) not null unique,
    cust_med decimal(10,2)
);

drop table if exists usuarios;
create table usuarios(
	id_user int primary key auto_increment,
    email varchar(50) not null unique,
    senha varchar(255) not null
);

drop table if exists viagem;
create table viagem(
	id_viagem int primary key auto_increment,
    id_user int not null,
    id_pais int not null,
    titulo varchar(20),
    data_viagem date,
    meta decimal(10,2),
    
    foreign key(id_user) references usuarios(id_user),
    foreign key(id_pais) references paises(id_pais)
);

drop table if exists movimentacoes;
create table movimentacoes(
	id_move int primary key auto_increment,
    id_viagem int not null,
    valor decimal(10,2),
    tipo enum("deposito","retirada"),
    data_move date,
    
    foreign key(id_viagem) references viagem(id_viagem)
);

drop table if exists anotacoes;
create table anotacoes(
	id_nota int primary key auto_increment,
    id_viagem int not null,
    anotacao varchar(300),
    
    foreign key(id_viagem) references viagem(id_viagem)
);

USE viagem_app;

-- 5 países
INSERT INTO paises (pais, moeda, cod_moeda, cust_med) VALUES
('Brasil','Real', 'BRL', 000.00),
('Japao', 'Iene', 'JPY', 850.00),
('Estados Unidos', 'Dolar', 'USD', 25.00),
('Franca', 'Euro', 'EUR', 18.50),
('Coreia do Sul', 'Won', 'KRW', 32000.00);


-- 1 usuário
INSERT INTO usuarios (email, senha) VALUES
('gabriel@email.com', '123456');


-- 5 viagens, uma para cada país
INSERT INTO viagem (id_user, id_pais, titulo, data_viagem, meta) VALUES
(1, 1, 'Viagem Brasil', '2026-12-15', 3000.00),
(1, 2, 'Viagem Japao', '2028-01-20', 15000.00),
(1, 3, 'Viagem EUA', '2027-07-10', 12000.00),
(1, 4, 'Viagem Franca', '2027-09-05', 10000.00),
(1, 5, 'Viagem Coreia', '2028-03-15', 13000.00);


-- 1 movimentação para cada viagem
INSERT INTO movimentacoes (id_viagem, valor, tipo, data_move) VALUES
(1, 500.00, 'deposito', '2026-08-11'),
(2, 200.00, 'deposito', '2026-08-11'),
(3, 300.00, 'deposito', '2026-08-11'),
(4, 150.00, 'deposito', '2026-08-11'),
(5, 250.00, 'deposito', '2026-08-11');


-- 1 anotação para cada viagem
INSERT INTO anotacoes (id_viagem, anotacao) VALUES
(1, 'Conhecer cidades historicas e praias do Brasil.'),
(2, 'Visitar Tokyo, Kyoto e assistir a um show.'),
(3, 'Conhecer Nova York e visitar os principais pontos turisticos.'),
(4, 'Visitar Paris, museus e pontos historicos.'),
(5, 'Conhecer Seoul e experimentar a culinaria local.');